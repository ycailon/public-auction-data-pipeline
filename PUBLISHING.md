# Publish this demo to a new public GitHub repository

**Suggested repository name:** `public-auction-data-pipeline`

1. On GitHub, create a new **public, empty** repository with the suggested name under `ycailon`. Do **not** initialize with a README, .gitignore or license; this package already includes them.
2. Extract the provided ZIP file, then open PowerShell in the extracted project root (where `README.md` lives).
3. Run:

```powershell
git init -b main
git add .
git commit -m "Add multi-source auction data engineering portfolio demo"
git remote add origin https://github.com/ycailon/public-auction-data-pipeline.git
git push -u origin main
```

4. Verify the visible README, fixtures and tests. You may update the tailored resume's portfolio section once the repository is published.

**Alternatively:** after you create the empty repository, tell ChatGPT its exact `owner/repo` name. The connected GitHub tool can add files to existing repositories.

**Do not treat the sample data as verified real property records.** Read `docs/source-quality-and-legal.md` before adapting it to live sources.
