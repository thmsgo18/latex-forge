| `biber` not found | `latex-forge build` installs it automatically, or `tlmgr install biber` |
| Bibliography not showing | Run `biber build/@@NAME@@` after the first lualatex pass |
| `I found no \bibdata command` | You ran `bibtex` instead of `biber` — use `biber` |
