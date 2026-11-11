Output assets/demo-cli.gif
Set Shell "bash"
Set FontSize 15
Set Width 1100
Set Height 720
Set Padding 18
Set Theme "Dracula"
Set TypingSpeed 40ms

Hide
Type "cd examples/shop && export FLOWSCOPE_PYTHON=$PWD/../../.venv/bin/python && PS1='$ ' && alias flow=../../bin/flow && clear" Enter
Show

Type "flow hld" Enter
Sleep 5s
Type "clear" Enter
Type 'flow run "small order"' Enter
Sleep 4s
Type "clear" Enter
Type "flow bottleneck" Enter
Sleep 6s
