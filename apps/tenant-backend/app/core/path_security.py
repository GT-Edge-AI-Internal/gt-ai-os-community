"""
Path Security Utilities for GT AI OS

Provides path sanitization and validation to prevent path traversal attacks.
"""
import re
from pathlib import Path
from typing import Optional


def sanitize_path_component(component: str) -> str:
    """
    Sanitize a single path component to prevent path traversal.

    Removes or replaces dangerous characters including:
    - Path separators (/ and \\)
    - Parent directory references (..)
    - Null bytes
    - Other special characters

    Args:
        component: The path component to sanitize

    Returns:
        Sanitized component safe for use in file paths
    """
    if not component:
        return ""

    # Remove null bytes
    sanitized = component.replace('\x00', '')

    # Remove path separators
    sanitized = re.sub(r'[/\\]', '', sanitized)

    # Remove parent directory references
    sanitized = sanitized.replace('..', '')

    # For tenant domains and similar identifiers, allow alphanumeric, hyphen, underscore
    # For filenames, allow alphanumeric, hyphen, underscore, and single dots
    sanitized = re.sub(r'[^a-zA-Z0-9_\-.]', '_', sanitized)

    # Prevent leading dots (hidden files) and multiple consecutive dots
    sanitized = re.sub(r'^\.+', '', sanitized)
    sanitized = re.sub(r'\.{2,}', '.', sanitized)

    return sanitized


def sanitize_tenant_domain(domain: str) -> str:
    """
    Sanitize a tenant domain for safe use in file paths.

    More restrictive than general path component sanitization.
    Only allows lowercase alphanumeric characters, hyphens, and underscores.

    Args:
        domain: The tenant domain to sanitize

    Returns:
        Sanitized domain safe for use in file paths
    """
    if not domain:
        raise ValueError("Tenant domain cannot be empty")

    # Convert to lowercase and sanitize
    sanitized = domain.lower()
    sanitized = re.sub(r'[^a-z0-9_\-]', '_', sanitized)
    sanitized = sanitized.strip('_-')

    if not sanitized:
        raise ValueError("Tenant domain resulted in empty string after sanitization")

    return sanitized


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename for safe storage.

    Preserves the file extension but sanitizes the rest.

    Args:
        filename: The filename to sanitize

    Returns:
        Sanitized filename
    """
    if not filename:
        return ""

    # Get the extension
    path = Path(filename)
    stem = path.stem
    suffix = path.suffix

    # Sanitize the stem (filename without extension)
    safe_stem = sanitize_path_component(stem)

    # Sanitize the extension (should just be alphanumeric)
    safe_suffix = ""
    if suffix:
        safe_suffix = '.' + re.sub(r'[^a-zA-Z0-9]', '', suffix[1:])

    result = safe_stem + safe_suffix

    if not result:
        result = "unnamed"

    return result


def safe_join_path(base: Path, *components: str, require_within_base: bool = True) -> Path:
    """
    Safely join path components, preventing traversal attacks.

    Args:
        base: The base directory that all paths must stay within
        components: Path components to join to the base
        require_within_base: If True, verify the result is within base

    Returns:
        The joined path

    Raises:
        ValueError: If the resulting path would be outside the base directory
    """
    if not base:
        raise ValueError("Base path cannot be empty")

    # Sanitize all components
    sanitized = [sanitize_path_component(c) for c in components if c]

    # Filter out empty components
    sanitized = [c for c in sanitized if c]

    if not sanitized:
        return base

    # Join the path
    result = base.joinpath(*sanitized)

    # Verify the result is within the base directory
    if require_within_base:
        try:
            resolved_base = base.resolve()
            resolved_result = result.resolve()

            # Check if result is within base
            resolved_result.relative_to(resolved_base)
        except (ValueError, RuntimeError):
            raise ValueError(f"Path traversal detected: result would be outside base directory")

    return result


def validate_file_extension(filename: str, allowed_extensions: Optional[list] = None) -> bool:
    """
    Validate that a file has an allowed extension.

    Args:
        filename: The filename to check
        allowed_extensions: List of allowed extensions (e.g., ['.txt', '.pdf']).
                          If None, all extensions are allowed.

    Returns:
        True if the extension is allowed, False otherwise
    """
    if allowed_extensions is None:
        return True

    path = Path(filename)
    extension = path.suffix.lower()

    return extension in [ext.lower() for ext in allowed_extensions]
