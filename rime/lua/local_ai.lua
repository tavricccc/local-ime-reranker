-- Final filter: keep the real candidate objects and all candidates after Top-N.
local M = {}

local function quote(value)
  return '"' .. value:gsub('[%z\1-\31\\"]', function(c)
    if c == '\\' then return '\\\\' end
    if c == '"' then return '\\"' end
    return string.format('\\u%04x', string.byte(c))
  end) .. '"'
end

local function tail(value, count)
  local n = utf8.len(value)
  if not n or n <= count then return value end
  return value:sub(utf8.offset(value, n - count + 1))
end

function M.init(env)
  env.budget = env.engine.schema.config:get_int('local_ai/budget_ms') or 80
  env.page_size = env.engine.schema.config:get_int('menu/page_size') or 8
  local loader = package.loadlib(rime_api.get_user_data_dir() .. '/lua/ai_bridge.dll', 'luaopen_ai_bridge')
  if loader then
    local ok, module = pcall(loader)
    if ok and type(module) == 'table' then env.bridge = module end
  end
  env.connection = env.engine.context.commit_notifier:connect(function(ctx)
    ctx:set_property('ai_recent', tail(ctx:get_property('ai_recent') .. ctx:get_commit_text(), 96))
  end)
end

function M.fini(env)
  if env.connection then env.connection:disconnect() end
end

function M.func(input, env)
  local context = env.engine.context
  -- Property notifications can replace Weasel's pending option toast. Keep
  -- diagnostic updates inside explicit test sessions, outside normal typing.
  local function report(name, value)
    if context:get_option('ai_diagnostics') then context:set_property(name, value) end
  end
  local head = {}
  local iterator, state = input:iter()
  for _ = 1, 48 do
    local candidate = iterator(state)
    if not candidate then break end
    head[#head + 1] = candidate
  end
  local records = {}
  for i, c in ipairs(head) do
    records[i] = string.format('{"text":%s,"quality":%.8g,"original_rank":%d,"start":%d,"end":%d,"type":%s,"preedit":%s}',
      quote(c.text), c.quality, i, c.start, c._end, quote(c.type), quote(c.preedit))
  end
  report('ai_snapshot', '{"candidates":[' .. table.concat(records, ',') .. ']}')
  local first = head[1]
  local eligible, positions = {}, {}
  if first then
    local groups, boundaries = {}, {}
    for i, c in ipairs(head) do
      if c.start == first.start then
        if not groups[c._end] then groups[c._end] = {}; boundaries[#boundaries + 1] = c._end end
        groups[c._end][#groups[c._end] + 1] = i
      end
    end
    -- Keep the original first choice, then distribute the model's larger pool
    -- over complete sentences and native prefixes rather than 16 homophones.
    local round = 1
    while #positions < 16 do
      local added = false
      for _, boundary in ipairs(boundaries) do
        local index = groups[boundary][round]
        if index and #positions < 16 then
          positions[#positions + 1] = index
          eligible[#eligible + 1] = records[index]
          added = true
        end
      end
      if not added then break end
      round = round + 1
    end
  end
  report('ai_pool_snapshot', '[' .. table.concat(eligible, ',') .. ']')
  local prior = context:get_property('ai_context')
  if prior == '' then prior = context:get_property('ai_recent') end
  local attempted = false
  -- Infer at complete syllables; unfinished phonetics stream straight through.
  if env.bridge and context:get_option('local_ai') and #eligible > 1 and prior ~= ''
      and context.input:match('[ 6347]$') then
    attempted = true
    local prefix = context:get_property('ai_prefix')
    local payload = '{"wire":"indices","allow_partial":true,"raw_input":' .. quote(context.input) .. ',"context":' .. quote(tail(prior, 96)) ..
      ',"prefix":' .. quote(prefix) .. ',"code":' .. quote(first.preedit) ..
      ',"candidates":[' .. table.concat(eligible, ',') .. ']}'
    local budget = tonumber(context:get_property('ai_budget_ms')) or env.budget
    local started = rime_api.get_time_ms()
    -- Decide once for this input/candidate/context snapshot. Busy/timeout must
    -- not turn into a later reorder while the user is selecting the same menu.
    local response
    if env.last_payload == payload then
      response = env.last_response
    else
      response = env.bridge.exchange(payload, budget)
      env.last_payload, env.last_response = payload, response
    end
    report('ai_elapsed_ms', tostring(rime_api.get_time_ms() - started))
    if response then
      local order, seen = {}, {}
      for token in response:gmatch('[^,]+') do
        local index = tonumber(token)
        if not index or index % 1 ~= 0 or not positions[index] or seen[index] then
          order = {}; break
        end
        seen[index] = true
        order[#order + 1] = index
      end
      if #order == #positions then
        local original = {}
        for i, index in ipairs(positions) do original[i] = head[index] end
        for i, index in ipairs(positions) do head[index] = original[order[i]] end
        report('ai_status', 'returned')
      else report('ai_status', 'invalid_response') end
    else report('ai_status', 'unavailable_or_timeout') end
  end
  if not attempted then report('ai_status', 'bypassed') end
  local function emit(candidate)
    local comment = candidate.comment
    if comment == 'AI 開' or comment == 'AI 關' then
      comment = ''
    else
      comment = comment:gsub('^AI 開 · ', ''):gsub('^AI 關 · ', '')
    end
    candidate.comment = comment
    yield(candidate)
  end
  for _, candidate in ipairs(head) do emit(candidate) end
  for candidate in iterator, state do emit(candidate) end
end

return M
