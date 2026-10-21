-- my-setup: files/hammerspoon_init.lua, deployed to ~/opt/my-setup/hammerspoon/init.lua by modules/hammerspoon.sh and
-- linked from ~/.hammerspoon/init.lua. Edit it in ~/dev/my-setup, then `INSTALL=true bash bootstrap.sh hammerspoon`.
--
-- 2-key shortcuts for the "Blocks" macro of the "Importants (new)" Sheet (~/dev/secrets-and-account-migration, work/tools/sheet_blocks/;
-- user, 2026-10-21): ⌥B new block, ⌥D remove the block, ⌥R redraw → the macro's own shortcuts ⌘⌥⇧1 / ⌘⌥⇧2 / ⌘⌥⇧3.
-- Only while the front window is a Chrome window whose title has "Importants"; anywhere else the keys type what they
-- always did.

local function inImportants()
  local w = hs.window.frontmostWindow()
  local app = w and w:application()
  return app ~= nil and app:bundleID() == "com.google.Chrome" and (w:title() or ""):find("Importants", 1, true) ~= nil
end

local function bind(key, digit)
  local hk
  hk = hs.hotkey.new({ "alt" }, key, function()
    if inImportants() then
      hs.eventtap.keyStroke({ "cmd", "alt", "shift" }, digit, 0)
    else -- not the Sheet: let ⌥<key> through as if nothing was bound
      hk:disable()
      hs.eventtap.keyStroke({ "alt" }, key, 0)
      hk:enable()
    end
  end)
  hk:enable()
end

bind("b", "1")
bind("d", "2")
bind("r", "3")

-- reload by itself when the deployed copy changes
ConfigWatcher = hs.pathwatcher.new(os.getenv("HOME") .. "/opt/my-setup/hammerspoon/", hs.reload):start()
hs.alert.show("Hammerspoon: ⌥B ⌥D ⌥R for the Importants blocks")
