# Static Assets for Control Panel Backend

This directory contains static assets used by the control panel backend services, particularly for email templates.

## Assets

### Email Resources (`assets/`)

- **gt-edge-ai-logo.png** - GT Edge AI logo used in email templates (password reset, notifications, etc.)
  - Source: `/apps/tenant-app/public/gt-edge-ai-new-logo.png`
  - Used in: Password reset emails with Content-ID: `<gt_logo>`
  - Dimensions: Optimized for email clients
  - Format: PNG with transparency

## Usage in Email Templates

The logo is embedded in emails using MIME multipart with Content-ID references:

```python
# In email.py
logo_img = MIMEImage(f.read())
logo_img.add_header('Content-ID', '<gt_logo>')
msg.attach(logo_img)
```

```html
<!-- In HTML email template -->
<img src="cid:gt_logo" alt="GT Edge AI" />
```

## Deployment Notes

- Ensure this directory and its contents are included in Docker images
- The logo file should be accessible at runtime for email generation
- Fallback paths are configured in `app/core/email.py` for different deployment scenarios
