# Vioum

Vioum est un scanner d'arnaques Mobile Money au Togo, construit avec Next.js et Gemma. Collez un SMS, ajoutez une capture ou activez `/apprendre` pour étudier un cours.

## Lancer le projet

```powershell
pnpm install
Copy-Item .env.example .env
# Ajoutez GEMINI_API_KEY dans .env
pnpm dev
```

Ouvrez `http://localhost:3000`.

## Hébergement

Le projet est prêt pour Vercel. Importez le dépôt, puis ajoutez `GEMINI_API_KEY` et, si besoin, `GEMINI_MODEL=gemma-4-26b-a4b-it` dans les variables d'environnement du projet. Pour activer les réponses locales vérifiées, ajoutez aussi `YODI_API_KEY` : Vioum traduit les analyses françaises avec Yodi vers l'Eʋegbe (`ewe_Latn`) ou le Kabyè (`kbp_Latn`). Ne mettez jamais une clé dans le navigateur ou dans Git.

## Commandes

- `/apprendre` active les révisions.
- `/resume` crée une fiche.
- `/plan` propose un calendrier.
- `/quiz` lance un entraînement.
- `/stop` revient au scanner.

Les fichiers sont envoyés à Gemma pour l'analyse et ne sont pas enregistrés par l'application. Une réponse ne confirme jamais une transaction : vérifiez le solde via le canal officiel.
