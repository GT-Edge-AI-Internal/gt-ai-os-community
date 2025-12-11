#!/usr/bin/env python3
"""
Test script to generate and preview password reset email HTML
"""

import sys
import os
import base64
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent / 'app'))

from app.core.email import create_password_reset_html

def generate_test_email():
    """Generate a test password reset email with embedded logo"""

    test_email = "user@example.com"
    test_token = "test_token_abc123xyz"
    test_reset_link = f"http://localhost:3002/reset-password?token={test_token}"

    html_content = create_password_reset_html(test_reset_link, test_email)

    # Convert cid:gt_logo to base64 data URL for preview
    logo_path = Path(__file__).parent / 'app' / 'static' / 'assets' / 'gt-edge-ai-logo.png'

    if logo_path.exists():
        with open(logo_path, 'rb') as img_file:
            logo_base64 = base64.b64encode(img_file.read()).decode('utf-8')
            logo_data_url = f"data:image/png;base64,{logo_base64}"

            # Replace cid:gt_logo with base64 data URL for browser preview
            html_content = html_content.replace('cid:gt_logo', logo_data_url)
            print(f"✅ Logo embedded as base64 data URL")
    else:
        print(f"⚠️  Logo not found at: {logo_path}")

    # Save to file
    output_file = Path(__file__).parent / 'password_reset_email_preview.html'
    with open(output_file, 'w') as f:
        f.write(html_content)

    print(f"✅ Test email HTML generated successfully!")
    print(f"📁 Saved to: {output_file}")
    print(f"\n📧 Email details:")
    print(f"   To: {test_email}")
    print(f"   Reset Link: {test_reset_link}")
    print(f"\n🌐 Open the file in a browser to preview:")
    print(f"   open {output_file}")

    return output_file

if __name__ == '__main__':
    generate_test_email()
