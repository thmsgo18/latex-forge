# Getting Started — @@NAME@@

## Workflow

**1. Modifier vos informations**

Ouvrez `sections/en-tete.tex` et renseignez votre nom, téléphone, email et liens GitHub/LinkedIn.

**2. Remplir chaque section**

Éditez les fichiers dans `sections/` — un fichier par rubrique.

**3. Sauvegarder pour compiler**

Sauvegardez `@@NAME@@.tex` dans VS Code → LaTeX Workshop compile automatiquement → PDF dans `build/@@NAME@@.pdf`.

---

## Structure des sections

| Fichier | Contenu |
|---|---|
| `sections/en-tete.tex` | Nom, contacts, résumé |
| `sections/formation.tex` | Diplômes et formations |
| `sections/experience.tex` | Expériences professionnelles |
| `sections/projets.tex` | Projets personnels et académiques |
| `sections/engagement.tex` | Engagements et associations |
| `sections/competences.tex` | Compétences techniques et langues |

---

## Opérations courantes

### Ajouter une expérience

Dans `sections/experience.tex`, ajoutez un bloc `\resumeSubheading` :

```latex
\resumeSubheading
  {Intitulé du poste}{mois 20XX -- mois 20XX}
  {Nom de l'entreprise}{Ville, France}
  \begin{itemize}[leftmargin=0.12in, label={}, itemsep=0pt]
    \item \small Description de vos missions.
  \end{itemize}
```

### Ajouter un projet

Dans `sections/projets.tex`, ajoutez un bloc `\resumeProjectHeading` :

```latex
\resumeProjectHeading
  {\textbf{\href{https://github.com/username/projet}{Nom -- Technologies}}}{Contexte}
  \begin{itemize}[leftmargin=0.12in, label={}, itemsep=0pt]
    \item \small Description du projet.
  \end{itemize}
```

---

## Si la compilation échoue

1. **LaTeX non installé** → `latex-forge setup --install-tex`
2. **LaTeX Workshop non installé** → installer depuis le panneau Extensions de VS Code
3. **Police introuvable** → vérifiez que TeX Live est à jour : `tlmgr update --all`
4. **Compilation bloquée** → supprimer le dossier `build/` et réessayer

Ce CV utilise **LuaLaTeX** (pour fontspec). Vérifiez:

```bash
lualatex --version
```

---

## Ressources

| Ressource | Lien |
|---|---|
| Overleaf — Modèles de CV | <https://www.overleaf.com/gallery/tagged/cv> |
| LaTeX Wikibook | <https://en.wikibooks.org/wiki/LaTeX> |
| fontawesome5 icônes | <https://mirrors.ctan.org/fonts/fontawesome5/doc/fontawesome5.pdf> |
