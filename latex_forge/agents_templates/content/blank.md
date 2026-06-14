### Add a new section

Either add directly to `sections/content.tex`, or:
1. Create `sections/my-section.tex`
2. Add `\input{sections/my-section.tex}` in `@@NAME@@.tex`

### Add an image

Place the image in the project folder, then:
```latex
\begin{figure}[h]
  \centering
  \includegraphics[width=0.8\linewidth]{my-image.png}
  \caption{Caption here.}
  \label{fig:my-label}
\end{figure}
```

### Add a bibliography

Add a `references.bib` file, then in `@@NAME@@.tex` before `\end{document}`:
```latex
\bibliographystyle{plain}
\bibliography{references}
```
Then cite with `\cite{key}` in your text.