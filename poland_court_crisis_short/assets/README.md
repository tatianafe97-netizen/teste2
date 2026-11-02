# B-roll drop folder

Put any `.mp4` / `.mov` / `.webm` clips or `.jpg` / `.png` stills here and re-run
`make_short.py`. They are automatically:

- scaled and centre-cropped to 1080x1920,
- given an equal share of the 50 s runtime (stills get a slow Ken Burns push-in),
- graded down (desaturated, darkened), blended under a navy tint and a dark vignette,
- composited **behind** all broadcast graphics and captions.

Files are processed in alphabetical order, so prefix them (`01_warsaw.mp4`, `02_tribunal.jpg`, ...)
to control the sequence. Only use footage you have the rights to publish.
