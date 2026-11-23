# Proposal for Omarchy: let users plug in their own screensaver

Draft for the Omarchy Suggestions discussions
(https://github.com/omacom/omarchy/discussions/categories/suggestions). Not part of the install.

---

**Title:** Allow a custom screensaver command (e.g. `~/.config/omarchy/screensaver`)

Omarchy's screensaver is a nice touch, and the branding commands let you change the art it
animates. But there's no way to swap in a different screensaver program: `omarchy-launch-screensaver`
always runs `-e omarchy-screensaver`, and since `/usr/share/omarchy/bin` comes first on `PATH`
for the shell and idle service, a user can't shadow it either.

I made an animated multi-monitor screensaver (link) and the only way to hook it in was to put a
folder ahead of Omarchy's on `PATH` from `~/.bashrc` and rewrite the launcher's command line at
run time. It works, but it's fragile and it touches people's shell config.

**Suggestion:** in `omarchy-launch-screensaver`, run a user's screensaver when one exists:

```bash
screensaver=omarchy-screensaver
if [[ -x ~/.config/omarchy/screensaver ]]; then
  screensaver=~/.config/omarchy/screensaver
fi
...
hypr_exec kitty --class=org.omarchy.screensaver ... -e "$screensaver" "$m"
```

Passing the monitor name (`$m`) as an argument would also let a screensaver lay itself out
across monitors. The stock `omarchy-screensaver` can simply ignore it.

This follows the pattern Omarchy already uses for user overrides (branding files, hooks), keeps
the stock behaviour unchanged for everyone else, and is a few lines in one script.

Happy to open a PR if this sounds good.
