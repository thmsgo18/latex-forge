### Ajouter une expérience

Dans `sections/experience.tex` :
```latex
\resumeSubheading
  {Intitulé du poste}{mois 20XX -- mois 20XX}
  {Entreprise}{Ville, France}
  \begin{itemize}[leftmargin=0.12in, label={}, itemsep=0pt]
    \item \small Description des missions.
  \end{itemize}
```

### Ajouter un projet

Dans `sections/projets.tex` :
```latex
\resumeProjectHeading
  {\textbf{\href{https://github.com/user/repo}{Nom -- Technologies}}}{Contexte}
  \begin{itemize}[leftmargin=0.12in, label={}, itemsep=0pt]
    \item \small Description.
  \end{itemize}
```