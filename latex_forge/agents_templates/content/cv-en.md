### Add a work experience

In `sections/experience.tex`:
```latex
\resumeSubheading
  {Job Title}{Month 20XX -- Month 20XX}
  {Company}{City, Country}
  \begin{itemize}[leftmargin=0.12in, label={}, itemsep=0pt]
    \item \small Description of responsibilities.
  \end{itemize}
```

### Add a project

In `sections/projects.tex`:
```latex
\resumeProjectHeading
  {\textbf{\href{https://github.com/user/repo}{Name -- Technologies}}}{Context}
  \begin{itemize}[leftmargin=0.12in, label={}, itemsep=0pt]
    \item \small Description.
  \end{itemize}
```