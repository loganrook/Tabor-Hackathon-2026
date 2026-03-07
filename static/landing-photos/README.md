# Landing page photos

These images are used on the public landing page (scrolling photo rows). They must be **committed and pushed** so everyone on the team gets them when they clone or pull the repo.

Do not add `static/landing-photos/` or `*.jpg` to `.gitignore` in this project.

**Optimization:** Images are sized at 400×400px and compressed for smooth scrolling. To re-optimize after adding or replacing photos, run from project root:

```bash
python scripts/optimize_landing_photos.py
```
