# rent-o-earno
rent o earno

## Demo data on Streamlit Cloud

The database file (`rental_app.db`) is git-ignored, so it is not deployed. On a fresh
deployment `v12.py` calls `ensure_demo_data()`, which runs `seed_v10.py` once when the
database has no products or regular users. The sample product images in `sample_images/`
are committed, so the seeded listings render correctly.

Before deploying, copy the contents of your local `.streamlit/secrets.toml` into the
Streamlit Cloud app's **Secrets** settings — especially the `[admin]`, `[[admins]]`, and
`[demo_users]` sections. Without `[demo_users]`, the seeder cannot create the demo
logins and the app will show a warning instead of sample data.

After pushing changes, use **Reboot app** in Streamlit Cloud to force a fresh seed.
Note that any data created while using the deployed app is stored in the container's
local filesystem and will be lost on redeploy/reboot; for persistent data, connect the
app to an external database.
