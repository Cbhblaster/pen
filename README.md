# Journal++ aka *jpp*

jpp is a modern Python journal application. It allows you to 
quickly jot down your thoughts right from the command line. All your journals 
will be stored as text, which means you can simply put them into cloud storage
or put it on a USB flash drive and access it from anywhere, even without jpp. 
It takes a lot of inspiration from [jrnl](https://github.com/jrnl-org/jrnl),
but is rewritten from the ground up in modern Python, making it easier to extend
and maintain. Currently, it is still in the beginner phase, but some nice
additional features are already planned. 

## Journaling
Writing about your daily routine has been linked to therapeutic health benefits 
like stress reduction[[1]](#1)[[2]](https://www.apa.org/monitor/jun02/writing).  
It's not necessary to journal every single day, because it shouldn't be a 
burden.
Instead, write whenever you feel like it, when you feel stressed by something, 
or when you just want to get something out of your mind but can't talk about it
with someone right now. 

You can even use your journal to track progress in your work, in the gym or 
on the race track. Having a place to note your achievements, personal records 
or maybe how much weight you lost over time is a great motivator, as you can
always look back and see how fast you progressed.


## Using jpp
To make a new entry, just type:
```
jpp
```
If you haven't run jpp on this machine before, a short setup script will start, 
asking about you preferences like which editor you want to use. `jpp` will 
always try to infer these settings from your environment variables and only ask
when necessary. However, you can always change the jpp configuration which is
by default located at `$HOME/.config/jpp`. You can, however, change this
location by exporting the `JPP_HOME` environment variable before running 
`jpp`. This is especially useful if you want to sync your work using Dropbox, 
Google Cloud or a similar cloud storage. In this case, you need to export the 
location of the synced directory. 


## (Planned) Features

 * Fully text based ✔
 * Multiple Journals ❌
 * Filtering by date, tag ❌
 * Fast Search ❌
 * Custom Prompts ❌
 * git sync ❌
 * Encryption ❌
 * Tags ❌
 * Easy Export to other formats ❌

## References

[1]: Smyth, Joshua M. (1999). Written emotional expression: Effect sizes, outcome types, and moderating variables.