# 🖋️ Pen - your command line diary

Pen allows you to quickly jot down your thoughts right from the command line. 
All your journals will be stored as text, which means you can simply put them into cloud storage
or on a USB flash drive and access it from anywhere, even without pen itself. 
It takes a lot of inspiration from [jrnl](https://github.com/jrnl-org/jrnl) and
tries to create a similar interface that is just as easy to use, but Pen is 
rewritten from the ground up in modern Python, aiming for a more stable 
and enhanced experience. Currently, Pen is still in an early stage, but some
nice additional features are planned. 
Windows is currently not supported. If you are on Windows (and not using WSL) and want 
to use Pen, leave an issue on GitHub and ask for support. 

## Journaling
Writing about your daily routine has been linked to therapeutic health benefits 
like stress reduction
[[1]](#1) [[2]](https://www.apa.org/monitor/jun02/writing).
For years, practitioners have used logs, questionnaires, journals and other
writing forms to help people heal from stresses and traumas.
It's not necessary to journal every single day, because it should not become a
burden.
However, when you feel like it would help get things off your mind, 
when you feel stressed by something or when you just want to go through an 
experience in your head again before forgetting too many details, writing it
down can be a very relieving and helpful experience.

Pen is also great just as a simple note-keeping app. You could for example 
create a journal called 'code' where you briefly describe the cool new library 
you learnt about today so you can go back to it later, or to describe how you 
solved a difficult programming problem.  

You can also use Pen to track progress in your work, in the gym or 
on the race track. Having a place to note your achievements, personal records 
or how much weight you lost over time is a great motivator, as you can
always look back and see how fast you progressed.


## Using Pen
To make a new entry, just type:
```
pen
```
If you haven't run Pen on this machine before, a short setup dialog will start, 
asking about your preferences like which editor you want to use. Pen will 
always try to infer these settings from your environment variables and only ask
when necessary. You can always change the way Pen behaves by changing its 
configuration which is by default located at `$HOME/.config/pen`. You can also
change the config file's location by exporting the `PEN_HOME` environment
variable before running `pen`. This is especially useful if you want to sync
your config using Dropbox, Google Cloud or a different cloud storage service.


## (Planned) Features

Implemented features are marked with a ✔.
The list is ordered by their planned implementation order, but the order may
change.

| Feature | ? | Note |
|---------|---|------|
| Fully text based | ✔ | |
| Uses your OS settings when possible<br>(from environment variables) | ✔ | $EDITOR, $VISUAL, $LC_TIME<br>and more!|
| Multiple Journals | ✔ | One can be set as default |
| Writing/Deleting/Editing entries | ✔ | |
| Journals as single file | ✔ |  |
| Plugin System | ✔\* | (\*still being extended)<br>based on [pluggy](https://github.com/pytest-dev/pluggy) |
| Extendable Import System | ✔ | supports imports from **jrnl** |
| Filtering by date, tag, starred |  | |
| Fast Search |  | |
| Tags |  | |
| Star entries (favourite) |  | |
| git sync |  | Can use cloud<br>to sync (Dropbox, etc.) |
| Journals as hierarchical directory |  |  |
| Encryption |  | |
| Custom Prompts |  | |
| Store in custom file formats | ✔ (1) | plugins can extend this!<br>currently implemented:<br> Markdown |
| Imports from other sources |  | None planned<br>plugins possible|

## References

[1]: Smyth, Joshua M. (1999). Written emotional expression: Effect sizes, outcome types, and moderating variables.
