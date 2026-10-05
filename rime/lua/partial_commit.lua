-- Commit a genuine Rime prefix through its native confirmation/learning path.
return function(key, env)
  if key:release() or key:ctrl() or key:alt() or key:shift() or key.keycode ~= 0xff0d then return 2 end
  local context = env.engine.context
  local candidate = context:get_selected_candidate()
  if not candidate or candidate._end >= #context.input then return 2 end
  local boundary = candidate._end
  local prefix = context.input:sub(1, boundary)
  local remaining = context.input:sub(boundary + 1)
  context:confirm_current_selection()
  context:clear_non_confirmed_composition()
  context.input = prefix
  context:commit()
  context.input = remaining
  return 1
end
