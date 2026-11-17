# WordPress location pages

This is a child theme for the Twenty Twenty-Five block theme. It uses native post meta rather than ACF, so a location's address, phone, hours, services, and FAQs are stored once and rendered into both the page and JSON-LD.

## LocalWP setup

1. Create a LocalWP site using WordPress and the Twenty Twenty-Five theme.
2. Copy `harbourline-child` into `app/public/wp-content/themes/`.
3. In the WordPress admin, activate **Harbourline Locations**.
4. From the site's shell, run `wp eval-file wp-content/themes/harbourline-child/seed-locations.php`. The seed script is idempotent and creates/updates both sample locations.
5. Visit Settings → Permalinks and click Save once to refresh the custom post type routes.

The Location editor includes three FAQ pairs, a booking URL, and the required clinic fields. The seed uses a call-to-book anchor because the brief supplies no real booking system. The JSON-LD is assembled from the same post meta as the visible page. It uses Schema.org `MedicalBusiness` and `medicalSpecialty: Physiotherapy`; the schema is not hand-typed into either page.

## Checks still requiring LocalWP and Chrome

This workspace does not have LocalWP, WordPress, or Chrome DevTools available, so these checks have not been performed:

- Confirm both seeded pages render in WordPress and their content appears in View Source.
- Paste each page's full HTML into the Rich Results Test Code tab and save screenshots here.
- Run Lighthouse on mobile before and after the theme change and record both scores.

The theme intentionally avoids remote fonts, page-builder scripts, and external images. Record actual Lighthouse measurements only after running the local site; no score or validation screenshot is claimed here.
