This repository contains a few miscellaneous extractor plugins for [yt-dlp](https://github.com/yt-dlp/yt-dlp#readme). 

## Installation

Requires yt-dlp `2023.01.02` or above.

You can install this package with pip:
```
python3 -m pip install -U https://github.com/ctengel//yt-dlp-verschiedenes/archive/master.zip
```

See [installing yt-dlp plugins](https://github.com/yt-dlp/yt-dlp#installing-plugins) for the other methods this plugin package can be installed.


## verus

The site serves two structurally different listings, so each gets its own
scheme rather than being guessed at:

| URL | what it does |
| --- | --- |
| `verus://HOST/` | unauthenticated listing — preview trailers, taken straight off the index |
| `verusauth://HOST/` | authenticated listing — links out to per-item download pages |
| `verusclip://HOST/PATH` | one authenticated item; emitted by `verusauth://`, rarely typed by hand |

Only `verusauth://` and `verusclip://` use credentials. `verus://` ignores them
and warns if you supply any, since passing the unauthenticated scheme when you
meant the other one otherwise looks like a working run that quietly yields
trailers.

The two listings also paginate differently, and each scheme knows its own way.
Give `verusauth://` a category URL and it walks the page number embedded in the
filename, starting from whatever page you named:

```
yt-dlp -n 'verusauth://HOST/members/categories/movies_1_d.html'
```

An authenticated URL that isn't in that `NAME_PAGE_SORT.html` form is fetched
once rather than paginated.

The authenticated pages offer several MP4 resolutions; `-f best` takes the
largest. Use `-F` to list them and `-f MP4_720p` (etc.) to pick one.


## Authentication

Credentials are read the standard yt-dlp way, via `-u`/`-p` or `.netrc`.

For `.netrc`, add a line using the extractor's machine name — `verus`, not the
site's hostname:

```
machine verus login USERNAME password PASSWORD
```

```
chmod 600 ~/.netrc
```

Then pass `-n`:

```
yt-dlp -n 'verusauth://HOST/'
```

**`.netrc` is only consulted when `-n`/`--netrc` is given.** Without it yt-dlp
never opens the file, and the pages come back with no download menu.
Run with `-v` and look for `Using netrc for verus authentication` to confirm; a
missing or misspelled machine line reports `No authenticators for verus`.

Alternatives: `--netrc-location PATH` for a file elsewhere, or `--netrc-cmd
'pass show yt-dlp/{}'` to pull credentials from a password manager (`{}` is
replaced with the machine name; this form does not need `-n`). Passwords
containing spaces or `#` must be double-quoted in `.netrc`.


## Development

See the [Plugin Development](https://github.com/yt-dlp/yt-dlp/wiki/Plugin-Development) section of the yt-dlp wiki.
