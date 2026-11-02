# assets/ — drop-in photo hook

Drop licensed news photos or dashcam stills here (`.jpg .jpeg .png .webp .bmp`).
On the next `./run.sh` each scene that gets a photo swaps its generated navy
backdrop for the photo with a slow **Ken Burns** zoom/pan, a navy grade and a
**dark vignette**; the broadcast graphics render on top with translucent panels.

| File name                                   | Goes to                         |
|---------------------------------------------|---------------------------------|
| `scene1_*` or `map_*`                       | 0–10 s flight-path map          |
| `scene2_*` or `telemetry_*`                 | 10–25 s altitude graph          |
| `scene3_*` or `summary_*`                   | 25–35 s incident summary        |
| `scene4_*` or `investigation_*`             | 35–45 s investigation + outro   |
| anything else                               | dealt round-robin to free scenes |

Optional `credits.txt` (one per line), shown top-right of that scene:

```
scene3_crash_site.jpg = PHOTO: AP / Jane Doe
```

Wire-service photos (AP, Reuters, Getty) need a license for use on YouTube;
always credit them. Everything in this folder except this README is git-ignored.
