### Add a new section

1. Create `sections/my-section.tex`
2. Add `\input{sections/my-section.tex}` at the right place in `@@NAME@@.tex`

### Add a bibliography reference

Add an entry to `references/references.bib`, then cite inline:
```latex
As shown in previous work~\cite{author2024}.
```

### Add appendices

Place `\startannexes` in `@@NAME@@.tex` where the appendices begin, then use `\subsection{...}` for each appendix (A, B, C…).

### Add an image

Place the file in `images/`, then:
```latex
\begin{figure}[h]
  \centering
  \includegraphics[width=0.8\linewidth]{my-image.png}
  \caption{Caption here.}
  \label{fig:my-label}
\end{figure}
```