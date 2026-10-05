-- A caret edit invalidates our session-local committed-text history. We do not
-- read other applications' text or assume that old text is still at the caret.
local navigation = {
  [0xff08] = true, [0xffff] = true, [0xff50] = true, [0xff57] = true,
  [0xff51] = true, [0xff52] = true, [0xff53] = true, [0xff54] = true,
  [0xff55] = true, [0xff56] = true, [0xff0d] = true,
}

return function(key, env)
  local context = env.engine.context
  if not context:is_composing() then
    local code = key.keycode
    if navigation[code] or (key:ctrl() and not key:alt() and
        (code == 97 or code == 65 or code == 120 or code == 88 or code == 118 or code == 86)) then
      context:set_property('ai_recent', '')
    end
  end
  return 2 -- kNoop: keep the normal Rime key handling.
end
