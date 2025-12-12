"""
CSV Helper Utility for Agent Bulk Import/Export

RFC 4180 compliant CSV parsing and serialization for GT 2.0 Agent configurations.
Handles array fields (pipe-separated), object fields (JSON strings), and validation.
"""

import csv
import json
import io
import re
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# CSV Schema Definition - All user-configurable fields
AGENT_CSV_COLUMNS = [
    'name',                      # Required
    'description',               # Optional
    'category',                  # Optional (default: 'general')
    'category_description',      # Optional - description for auto-created categories
    'model',                     # Required
    'temperature',               # Optional (default: 0.7)
    'max_tokens',                # Optional (default: 4096)
    'prompt_template',           # Optional
    'dataset_connection',        # Optional (all/none/selected, default: 'all')
    'selected_dataset_ids',      # Optional (pipe-separated UUIDs)
    'disclaimer',                # Optional (max 500 chars)
    'easy_prompts',              # Optional (pipe-separated, max 10)
    'visibility',                # Optional (individual/team/organization, default: 'individual')
    'tags',                      # Optional (comma-separated)
]

# Required fields
REQUIRED_FIELDS = ['name', 'model']

# Enum validation
VALID_DATASET_CONNECTIONS = ['all', 'none', 'selected']
VALID_VISIBILITIES = ['individual', 'team', 'organization']
# Categories are now dynamic (Issue #215) - no hardcoded validation
# Categories will be auto-created if they don't exist during import
DEFAULT_AGENT_TYPE = 'general'

# Length limits
MAX_NAME_LENGTH = 255
MAX_DESCRIPTION_LENGTH = 1000
MAX_DISCLAIMER_LENGTH = 500
MAX_EASY_PROMPTS = 10


class CSVValidationError(Exception):
    """Raised when CSV validation fails"""
    def __init__(self, row_number: int, field: str, message: str):
        self.row_number = row_number
        self.field = field
        self.message = message
        super().__init__(f"Row {row_number}, field '{field}': {message}")


class AgentCSVHelper:
    """Helper class for Agent CSV import/export operations"""

    @staticmethod
    def normalize_agent_type(category: str) -> Tuple[str, bool]:
        """
        Normalize agent_type/category value.

        Categories are now dynamic (Issue #215) - any category is valid.
        Categories will be auto-created during agent import if they don't exist.

        Args:
            category: Raw category value from CSV

        Returns:
            Tuple of (normalized_category, was_corrected)
            - normalized_category: Normalized category slug
            - was_corrected: True if default was used (empty input)
        """
        if not category:
            return DEFAULT_AGENT_TYPE, True

        # Normalize to lowercase slug format
        category_slug = category.lower().strip()
        # Replace spaces and special chars with hyphens for slug
        category_slug = re.sub(r'[^a-z0-9]+', '-', category_slug).strip('-')

        if not category_slug:
            return DEFAULT_AGENT_TYPE, True

        return category_slug, False

    @staticmethod
    def parse_csv(csv_content: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Parse CSV content and validate agent data.

        Args:
            csv_content: CSV string content

        Returns:
            Tuple of (valid_agents, errors)
            - valid_agents: List of validated agent dictionaries
            - errors: List of error dictionaries with row_number, field, message
        """
        valid_agents = []
        errors = []

        try:
            # Parse CSV using RFC 4180 compliant parser
            csv_reader = csv.DictReader(io.StringIO(csv_content))

            # Validate header
            if not csv_reader.fieldnames:
                errors.append({
                    'row_number': 0,
                    'field': 'header',
                    'message': 'CSV header row is missing'
                })
                return valid_agents, errors

            # Check for required columns in header
            missing_cols = set(REQUIRED_FIELDS) - set(csv_reader.fieldnames)
            if missing_cols:
                errors.append({
                    'row_number': 0,
                    'field': 'header',
                    'message': f"Missing required columns: {', '.join(missing_cols)}"
                })
                return valid_agents, errors

            # Process each row
            for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 (1 is header)
                try:
                    agent_data = AgentCSVHelper._parse_row(row, row_num)
                    valid_agents.append(agent_data)
                except CSVValidationError as e:
                    errors.append({
                        'row_number': e.row_number,
                        'field': e.field,
                        'message': e.message
                    })
                except Exception as e:
                    errors.append({
                        'row_number': row_num,
                        'field': 'unknown',
                        'message': f"Unexpected error: {str(e)}"
                    })
                    logger.exception(f"Unexpected error parsing row {row_num}")

        except Exception as e:
            errors.append({
                'row_number': 0,
                'field': 'csv',
                'message': f"CSV parsing failed: {str(e)}"
            })
            logger.exception("CSV parsing failed")

        return valid_agents, errors

    @staticmethod
    def _parse_row(row: Dict[str, str], row_num: int) -> Dict[str, Any]:
        """
        Parse and validate a single CSV row.

        Args:
            row: CSV row as dictionary
            row_num: Row number for error reporting

        Returns:
            Validated agent data dictionary

        Raises:
            CSVValidationError: If validation fails
        """
        agent_data = {}

        # Required fields
        for field in REQUIRED_FIELDS:
            value = row.get(field, '').strip()
            if not value:
                raise CSVValidationError(row_num, field, f"Required field '{field}' is empty")
            agent_data[field] = value

        # Validate name length
        if len(agent_data['name']) > MAX_NAME_LENGTH:
            raise CSVValidationError(row_num, 'name', f"Name exceeds {MAX_NAME_LENGTH} characters")

        # Optional string fields
        description = row.get('description', '').strip()
        if description:
            if len(description) > MAX_DESCRIPTION_LENGTH:
                raise CSVValidationError(row_num, 'description', f"Description exceeds {MAX_DESCRIPTION_LENGTH} characters")
            agent_data['description'] = description

        category = row.get('category', '').strip()
        # Normalize and validate agent_type
        normalized_category, was_corrected = AgentCSVHelper.normalize_agent_type(category)
        agent_data['category'] = normalized_category
        if was_corrected and category:  # Only log if there was an input that needed correction
            logger.info(f"Row {row_num}: Agent type '{category}' auto-corrected to '{normalized_category}'")

        # Category description for auto-created categories
        category_description = row.get('category_description', '').strip()
        if category_description:
            agent_data['category_description'] = category_description

        prompt_template = row.get('prompt_template', '').strip()
        if prompt_template:
            agent_data['prompt_template'] = prompt_template

        # Numeric fields with defaults
        temperature_str = row.get('temperature', '').strip()
        if temperature_str:
            try:
                temperature = float(temperature_str)
                if not 0.0 <= temperature <= 2.0:
                    raise CSVValidationError(row_num, 'temperature', "Temperature must be between 0.0 and 2.0")
                agent_data['temperature'] = temperature
            except ValueError:
                raise CSVValidationError(row_num, 'temperature', f"Invalid number: '{temperature_str}'")

        max_tokens_str = row.get('max_tokens', '').strip()
        if max_tokens_str:
            try:
                max_tokens = int(max_tokens_str)
                if max_tokens <= 0:
                    raise CSVValidationError(row_num, 'max_tokens', "max_tokens must be positive")
                agent_data['max_tokens'] = max_tokens
            except ValueError:
                raise CSVValidationError(row_num, 'max_tokens', f"Invalid integer: '{max_tokens_str}'")

        # Enum fields
        dataset_connection = row.get('dataset_connection', '').strip().lower()
        if dataset_connection:
            if dataset_connection not in VALID_DATASET_CONNECTIONS:
                raise CSVValidationError(row_num, 'dataset_connection',
                    f"Invalid value '{dataset_connection}'. Must be one of: {', '.join(VALID_DATASET_CONNECTIONS)}")
            agent_data['dataset_connection'] = dataset_connection

        visibility = row.get('visibility', '').strip().lower()
        if visibility:
            if visibility not in VALID_VISIBILITIES:
                raise CSVValidationError(row_num, 'visibility',
                    f"Invalid value '{visibility}'. Must be one of: {', '.join(VALID_VISIBILITIES)}")
            agent_data['visibility'] = visibility

        # Array fields (pipe-separated)
        selected_dataset_ids = row.get('selected_dataset_ids', '').strip()
        if selected_dataset_ids:
            ids = [id.strip() for id in selected_dataset_ids.split('|') if id.strip()]
            # Validate UUID format
            uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
            for dataset_id in ids:
                if not uuid_pattern.match(dataset_id):
                    raise CSVValidationError(row_num, 'selected_dataset_ids', f"Invalid UUID format: '{dataset_id}'")
            agent_data['selected_dataset_ids'] = ids

        easy_prompts_str = row.get('easy_prompts', '').strip()
        if easy_prompts_str:
            prompts = [p.strip() for p in easy_prompts_str.split('|') if p.strip()]
            if len(prompts) > MAX_EASY_PROMPTS:
                raise CSVValidationError(row_num, 'easy_prompts', f"Maximum {MAX_EASY_PROMPTS} easy prompts allowed")
            agent_data['easy_prompts'] = prompts

        tags_str = row.get('tags', '').strip()
        if tags_str:
            tags = [t.strip() for t in tags_str.split(',') if t.strip()]
            agent_data['tags'] = tags

        # Disclaimer with length check
        disclaimer = row.get('disclaimer', '').strip()
        if disclaimer:
            if len(disclaimer) > MAX_DISCLAIMER_LENGTH:
                raise CSVValidationError(row_num, 'disclaimer', f"Disclaimer exceeds {MAX_DISCLAIMER_LENGTH} characters")
            agent_data['disclaimer'] = disclaimer

        return agent_data

    @staticmethod
    def serialize_agent_to_csv(agent: Dict[str, Any]) -> str:
        """
        Serialize a single agent to CSV format.

        Args:
            agent: Agent data dictionary

        Returns:
            CSV string with header and single row
        """
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=AGENT_CSV_COLUMNS, extrasaction='ignore')

        # Write header
        writer.writeheader()

        # Prepare row data
        row_data = {}

        # Simple string fields with direct mapping
        for field in ['name', 'description', 'model', 'prompt_template', 'disclaimer', 'visibility']:
            if field in agent and agent[field]:
                row_data[field] = str(agent[field])

        # Map agent_type to category
        if 'agent_type' in agent and agent['agent_type']:
            row_data['category'] = str(agent['agent_type'])
        elif 'category' in agent and agent['category']:
            row_data['category'] = str(agent['category'])

        # Category description (fetched from categories table in export endpoint)
        if 'category_description' in agent and agent['category_description']:
            row_data['category_description'] = str(agent['category_description'])

        # Dataset connection
        if 'dataset_connection' in agent and agent['dataset_connection']:
            row_data['dataset_connection'] = str(agent['dataset_connection'])

        # Numeric fields
        if 'temperature' in agent and agent['temperature'] is not None:
            row_data['temperature'] = str(agent['temperature'])
        if 'max_tokens' in agent and agent['max_tokens'] is not None:
            row_data['max_tokens'] = str(agent['max_tokens'])

        # Array fields (pipe-separated)
        if 'selected_dataset_ids' in agent and agent['selected_dataset_ids']:
            row_data['selected_dataset_ids'] = '|'.join(agent['selected_dataset_ids'])

        if 'easy_prompts' in agent and agent['easy_prompts']:
            row_data['easy_prompts'] = '|'.join(agent['easy_prompts'])

        if 'tags' in agent and agent['tags']:
            row_data['tags'] = ','.join(agent['tags'])

        # Write row
        writer.writerow(row_data)

        return output.getvalue()

    @staticmethod
    def generate_unique_name(base_name: str, existing_names: List[str]) -> str:
        """
        Generate a unique agent name by appending (1), (2), etc. if duplicates exist.

        Args:
            base_name: Original agent name
            existing_names: List of existing agent names to check against

        Returns:
            Unique agent name
        """
        # If no conflict, return as-is
        if base_name not in existing_names:
            return base_name

        # Find highest suffix number
        pattern = re.compile(rf'^{re.escape(base_name)} \((\d+)\)$')
        max_suffix = 0

        for name in existing_names:
            match = pattern.match(name)
            if match:
                suffix = int(match.group(1))
                max_suffix = max(max_suffix, suffix)

        # Generate next available name
        next_suffix = max_suffix + 1
        return f"{base_name} ({next_suffix})"

    @staticmethod
    def validate_csv_size(csv_content: str, max_size_mb: float = 1.0) -> bool:
        """
        Validate CSV content size.

        Args:
            csv_content: CSV string
            max_size_mb: Maximum size in megabytes

        Returns:
            True if valid, False if too large
        """
        size_bytes = len(csv_content.encode('utf-8'))
        max_bytes = max_size_mb * 1024 * 1024
        return size_bytes <= max_bytes
