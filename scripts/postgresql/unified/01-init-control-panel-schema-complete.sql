--
-- PostgreSQL database dump
--

-- Dumped from database version 15.14
-- Dumped by pg_dump version 15.14

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: admin_control; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA admin_control;


--
-- Name: SCHEMA admin_control; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA admin_control IS 'GT 2.0 Admin Control Panel Schema with HA Support';


--
-- Name: pg_buffercache; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_buffercache WITH SCHEMA public;


--
-- Name: EXTENSION pg_buffercache; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pg_buffercache IS 'examine the shared buffer cache';


--
-- Name: pg_stat_statements; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_stat_statements WITH SCHEMA public;


--
-- Name: EXTENSION pg_stat_statements; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pg_stat_statements IS 'track planning and execution statistics of all SQL statements executed';


--
-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;


--
-- Name: EXTENSION "uuid-ossp"; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: api_keys; Type: TABLE; Schema: admin_control; Owner: -
--

CREATE TABLE admin_control.api_keys (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    key_name character varying(255) NOT NULL,
    provider character varying(100) NOT NULL,
    encrypted_key text NOT NULL,
    key_hash character varying(255) NOT NULL,
    scopes jsonb DEFAULT '[]'::jsonb,
    usage_limits jsonb DEFAULT '{}'::jsonb,
    status character varying(50) DEFAULT 'active'::character varying,
    expires_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: model_registry; Type: TABLE; Schema: admin_control; Owner: -
--

CREATE TABLE admin_control.model_registry (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    name character varying(255) NOT NULL,
    provider character varying(100) NOT NULL,
    model_id character varying(255) NOT NULL,
    configuration jsonb DEFAULT '{}'::jsonb NOT NULL,
    pricing jsonb DEFAULT '{}'::jsonb,
    capabilities jsonb DEFAULT '{}'::jsonb,
    status character varying(50) DEFAULT 'active'::character varying,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: system_config; Type: TABLE; Schema: admin_control; Owner: -
--

CREATE TABLE admin_control.system_config (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    config_key character varying(255) NOT NULL,
    config_value jsonb NOT NULL,
    description text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: system_metrics; Type: TABLE; Schema: admin_control; Owner: -
--

CREATE TABLE admin_control.system_metrics (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    metric_name character varying(255) NOT NULL,
    metric_value numeric NOT NULL,
    metric_unit character varying(50),
    tags jsonb DEFAULT '{}'::jsonb,
    "timestamp" timestamp with time zone DEFAULT now(),
    tenant_id uuid
);


--
-- Name: tenants; Type: TABLE; Schema: admin_control; Owner: -
--

CREATE TABLE admin_control.tenants (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    domain character varying(255) NOT NULL,
    name character varying(255) NOT NULL,
    status character varying(50) DEFAULT 'active'::character varying,
    configuration jsonb DEFAULT '{}'::jsonb,
    resource_limits jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: ai_resources; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_resources (
    id integer NOT NULL,
    uuid character varying(36) NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    resource_type character varying(50) NOT NULL,
    provider character varying(50) NOT NULL,
    model_name character varying(100),
    resource_subtype character varying(50),
    personalization_mode character varying(20) NOT NULL,
    api_endpoints json NOT NULL,
    primary_endpoint text,
    api_key_encrypted text,
    failover_endpoints json NOT NULL,
    health_check_url text,
    iframe_url text,
    sandbox_config json NOT NULL,
    auth_config json NOT NULL,
    max_requests_per_minute integer NOT NULL,
    max_tokens_per_request integer NOT NULL,
    cost_per_1k_tokens double precision NOT NULL,
    latency_sla_ms integer NOT NULL,
    configuration json NOT NULL,
    health_status character varying(20) NOT NULL,
    last_health_check timestamp with time zone,
    is_active boolean NOT NULL,
    priority integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: ai_resources_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ai_resources_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ai_resources_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ai_resources_id_seq OWNED BY public.ai_resources.id;


--
-- Name: audit_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_logs (
    id integer NOT NULL,
    user_id integer,
    tenant_id integer,
    action character varying(100) NOT NULL,
    resource_type character varying(50),
    resource_id character varying(100),
    details json NOT NULL,
    ip_address character varying(45),
    user_agent text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: audit_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.audit_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: audit_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.audit_logs_id_seq OWNED BY public.audit_logs.id;


--
-- Name: billing_plans; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.billing_plans (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    display_name character varying(200),
    description character varying(500),
    base_price_cents integer,
    compute_price_per_hour_cents integer,
    storage_price_per_gb_month_cents integer,
    api_price_per_1k_calls_cents integer,
    transfer_price_per_gb_cents integer,
    included_compute_hours integer,
    included_storage_gb integer,
    included_api_calls integer,
    included_transfer_gb integer,
    max_users integer,
    max_resources integer,
    max_storage_gb integer,
    features json,
    is_active boolean,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


--
-- Name: billing_plans_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.billing_plans_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: billing_plans_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.billing_plans_id_seq OWNED BY public.billing_plans.id;


--
-- Name: billing_usage; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.billing_usage (
    id integer NOT NULL,
    tenant_id integer NOT NULL,
    billing_date timestamp with time zone NOT NULL,
    billing_period character varying(20),
    total_cost_cents integer,
    compute_cost_cents integer,
    storage_cost_cents integer,
    api_cost_cents integer,
    transfer_cost_cents integer,
    compute_hours numeric(10,2),
    storage_gb_hours numeric(10,2),
    api_calls integer,
    data_transfer_gb numeric(10,2),
    resource_usage json,
    status character varying(20),
    invoice_id character varying(100),
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


--
-- Name: billing_usage_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.billing_usage_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: billing_usage_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.billing_usage_id_seq OWNED BY public.billing_usage.id;


--
-- Name: license_billing_usage; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.license_billing_usage (
    id integer NOT NULL,
    license_id integer NOT NULL,
    tenant_id integer NOT NULL,
    billing_period_start timestamp with time zone NOT NULL,
    billing_period_end timestamp with time zone NOT NULL,
    active_users integer,
    active_resources integer,
    resource_usage json,
    total_api_calls integer,
    total_tokens_used integer,
    total_storage_gb numeric(10,2),
    base_cost numeric(10,2),
    resource_cost numeric(10,2),
    total_cost numeric(10,2),
    invoice_status character varying(20),
    invoice_number character varying(50),
    payment_date timestamp with time zone,
    calculated_at timestamp with time zone DEFAULT now(),
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: license_billing_usage_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.license_billing_usage_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: license_billing_usage_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.license_billing_usage_id_seq OWNED BY public.license_billing_usage.id;


--
-- Name: license_seats; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.license_seats (
    id integer NOT NULL,
    license_id integer NOT NULL,
    user_id integer NOT NULL,
    seat_type character varying(50),
    is_active boolean,
    resource_overrides json,
    assigned_at timestamp with time zone DEFAULT now(),
    last_accessed timestamp with time zone,
    expires_at timestamp with time zone,
    CONSTRAINT check_seat_active_bool CHECK ((is_active = ANY (ARRAY[true, false])))
);


--
-- Name: license_seats_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.license_seats_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: license_seats_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.license_seats_id_seq OWNED BY public.license_seats.id;


--
-- Name: licenses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.licenses (
    id integer NOT NULL,
    license_uuid character varying(36) NOT NULL,
    tenant_id integer NOT NULL,
    license_key character varying(100) NOT NULL,
    license_type character varying(50) NOT NULL,
    max_seats integer NOT NULL,
    used_seats integer NOT NULL,
    allowed_resources json NOT NULL,
    resource_limits json NOT NULL,
    feature_flags json NOT NULL,
    billing_status character varying(20) NOT NULL,
    billing_cycle character varying(20) NOT NULL,
    price_per_seat numeric(10,2) NOT NULL,
    resource_multiplier numeric(5,2) NOT NULL,
    grace_period_days integer,
    enforcement_mode character varying(20),
    suspension_reason character varying(255),
    valid_from timestamp with time zone DEFAULT now() NOT NULL,
    valid_until timestamp with time zone NOT NULL,
    last_validated timestamp with time zone,
    grace_period_ends timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone,
    created_by character varying(255),
    last_modified_by character varying(255),
    CONSTRAINT check_positive_multiplier CHECK ((resource_multiplier > (0)::numeric)),
    CONSTRAINT check_positive_price CHECK ((price_per_seat >= (0)::numeric)),
    CONSTRAINT check_positive_seats CHECK ((used_seats >= 0)),
    CONSTRAINT check_seat_limit CHECK ((used_seats <= max_seats))
);


--
-- Name: licenses_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.licenses_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: licenses_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.licenses_id_seq OWNED BY public.licenses.id;


--
-- Name: model_configs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.model_configs (
    model_id character varying(255) NOT NULL,
    name character varying(255) NOT NULL,
    version character varying(50),
    provider character varying(50) NOT NULL,
    model_type character varying(50) NOT NULL,
    endpoint character varying(500) NOT NULL,
    api_key_name character varying(100),
    context_window integer,
    max_tokens integer,
    dimensions integer,
    capabilities json,
    cost_per_million_input double precision,
    cost_per_million_output double precision,
    description text,
    config json,
    is_active boolean,
    is_compound boolean DEFAULT false,
    health_status character varying(20),
    last_health_check timestamp without time zone,
    request_count integer,
    error_count integer,
    success_rate double precision,
    avg_latency_ms double precision,
    tenant_restrictions json,
    required_capabilities json,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


--
-- Name: model_usage_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.model_usage_logs (
    id integer NOT NULL,
    model_id character varying(255) NOT NULL,
    tenant_id character varying(100) NOT NULL,
    user_id character varying(100) NOT NULL,
    tokens_input integer,
    tokens_output integer,
    tokens_total integer,
    cost double precision,
    latency_ms double precision,
    success boolean,
    error_message text,
    request_id character varying(100),
    "timestamp" timestamp without time zone
);


--
-- Name: model_usage_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.model_usage_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: model_usage_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.model_usage_logs_id_seq OWNED BY public.model_usage_logs.id;


--
-- Name: password_reset_rate_limits; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.password_reset_rate_limits (
    id integer NOT NULL,
    email character varying(255) NOT NULL,
    request_count integer DEFAULT 1 NOT NULL,
    window_start timestamp with time zone NOT NULL,
    window_end timestamp with time zone NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: password_reset_rate_limits_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.password_reset_rate_limits_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: password_reset_rate_limits_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.password_reset_rate_limits_id_seq OWNED BY public.password_reset_rate_limits.id;


--
-- Name: resource_alerts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.resource_alerts (
    id integer NOT NULL,
    tenant_id integer NOT NULL,
    resource_type character varying(50) NOT NULL,
    alert_level character varying(20) NOT NULL,
    message text NOT NULL,
    current_usage double precision NOT NULL,
    max_value double precision NOT NULL,
    percentage_used double precision NOT NULL,
    acknowledged boolean NOT NULL,
    acknowledged_by character varying(100),
    acknowledged_at timestamp without time zone,
    created_at timestamp without time zone NOT NULL
);


--
-- Name: resource_alerts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.resource_alerts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: resource_alerts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.resource_alerts_id_seq OWNED BY public.resource_alerts.id;


--
-- Name: resource_pricing; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.resource_pricing (
    id integer NOT NULL,
    resource_id integer NOT NULL,
    pricing_model character varying(50),
    base_price numeric(10,4),
    unit_type character varying(50),
    tier_pricing json,
    standard_multiplier numeric(5,2),
    professional_multiplier numeric(5,2),
    enterprise_multiplier numeric(5,2),
    effective_from timestamp with time zone DEFAULT now(),
    effective_until timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


--
-- Name: resource_pricing_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.resource_pricing_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: resource_pricing_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.resource_pricing_id_seq OWNED BY public.resource_pricing.id;


--
-- Name: resource_quotas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.resource_quotas (
    id integer NOT NULL,
    tenant_id integer NOT NULL,
    resource_type character varying(50) NOT NULL,
    max_value double precision NOT NULL,
    current_usage double precision NOT NULL,
    warning_threshold double precision NOT NULL,
    critical_threshold double precision NOT NULL,
    unit character varying(20) NOT NULL,
    cost_per_unit double precision NOT NULL,
    is_active boolean NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: resource_quotas_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.resource_quotas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: resource_quotas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.resource_quotas_id_seq OWNED BY public.resource_quotas.id;


--
-- Name: resource_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.resource_templates (
    id integer NOT NULL,
    name character varying(50) NOT NULL,
    display_name character varying(100) NOT NULL,
    description text,
    template_data text NOT NULL,
    monthly_cost double precision NOT NULL,
    is_active boolean NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: resource_templates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.resource_templates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: resource_templates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.resource_templates_id_seq OWNED BY public.resource_templates.id;


--
-- Name: resource_usage; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.resource_usage (
    id integer NOT NULL,
    tenant_id integer NOT NULL,
    resource_type character varying(50) NOT NULL,
    usage_amount double precision NOT NULL,
    cost double precision NOT NULL,
    "timestamp" timestamp without time zone NOT NULL,
    usage_metadata text,
    user_id character varying(100),
    service character varying(50)
);


--
-- Name: resource_usage_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.resource_usage_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: resource_usage_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.resource_usage_id_seq OWNED BY public.resource_usage.id;


--
-- Name: session_data; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.session_data (
    id integer NOT NULL,
    uuid character varying(36) NOT NULL,
    user_id integer NOT NULL,
    tenant_id integer NOT NULL,
    resource_id integer NOT NULL,
    session_id character varying(100) NOT NULL,
    data_type character varying(50) NOT NULL,
    data_content json NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    auto_cleanup boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    last_accessed timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: session_data_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.session_data_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: session_data_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.session_data_id_seq OWNED BY public.session_data.id;


--
-- Name: system_metrics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.system_metrics (
    id integer NOT NULL,
    metric_name character varying(100) NOT NULL,
    metric_value double precision NOT NULL,
    metric_unit character varying(20) NOT NULL,
    "timestamp" timestamp without time zone NOT NULL,
    metric_metadata text
);


--
-- Name: system_metrics_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.system_metrics_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: system_metrics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.system_metrics_id_seq OWNED BY public.system_metrics.id;


--
-- Name: tenant_model_configs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tenant_model_configs (
    id integer NOT NULL,
    tenant_id integer NOT NULL,
    model_id character varying(255) NOT NULL,
    is_enabled boolean NOT NULL,
    tenant_capabilities json,
    rate_limits json,
    usage_constraints json,
    priority integer NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: tenant_model_configs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tenant_model_configs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tenant_model_configs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.tenant_model_configs_id_seq OWNED BY public.tenant_model_configs.id;


--
-- Name: tenant_resources; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tenant_resources (
    id integer NOT NULL,
    tenant_id integer NOT NULL,
    resource_id integer NOT NULL,
    usage_limits json NOT NULL,
    is_enabled boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: tenant_resources_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tenant_resources_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tenant_resources_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.tenant_resources_id_seq OWNED BY public.tenant_resources.id;


--
-- Name: tenant_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tenant_templates (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    template_data jsonb NOT NULL,
    is_default boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: tenant_templates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tenant_templates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tenant_templates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.tenant_templates_id_seq OWNED BY public.tenant_templates.id;


--
-- Name: tenants; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tenants (
    id integer NOT NULL,
    uuid character varying(36) NOT NULL,
    name character varying(100) NOT NULL,
    domain character varying(50) NOT NULL,
    template character varying(20) NOT NULL,
    status character varying(20) NOT NULL,
    max_users integer NOT NULL,
    resource_limits json NOT NULL,
    namespace character varying(100) NOT NULL,
    subdomain character varying(50) NOT NULL,
    database_path character varying(255),
    encryption_key text,
    api_keys json,
    api_key_encryption_version character varying(20),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    frontend_url character varying(255),
    optics_enabled boolean DEFAULT false
);


--
-- Name: tenants_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tenants_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tenants_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.tenants_id_seq OWNED BY public.tenants.id;


--
-- Name: tfa_verification_rate_limits; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tfa_verification_rate_limits (
    id integer NOT NULL,
    user_id integer NOT NULL,
    request_count integer DEFAULT 1 NOT NULL,
    window_start timestamp with time zone NOT NULL,
    window_end timestamp with time zone NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: tfa_verification_rate_limits_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tfa_verification_rate_limits_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tfa_verification_rate_limits_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.tfa_verification_rate_limits_id_seq OWNED BY public.tfa_verification_rate_limits.id;


--
-- Name: usage_records; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usage_records (
    id integer NOT NULL,
    tenant_id integer NOT NULL,
    resource_id integer NOT NULL,
    user_email character varying(255) NOT NULL,
    request_type character varying(50) NOT NULL,
    tokens_used integer NOT NULL,
    cost_cents integer NOT NULL,
    request_metadata json NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: usage_records_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.usage_records_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: usage_records_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.usage_records_id_seq OWNED BY public.usage_records.id;


--
-- Name: used_temp_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.used_temp_tokens (
    id integer NOT NULL,
    token_id character varying(255) NOT NULL,
    user_id integer NOT NULL,
    used_at timestamp with time zone DEFAULT now(),
    expires_at timestamp with time zone NOT NULL,
    user_email character varying,
    tfa_configured boolean,
    qr_code_uri text,
    manual_entry_key character varying,
    created_at timestamp without time zone,
    temp_token text
);


--
-- Name: used_temp_tokens_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.used_temp_tokens_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: used_temp_tokens_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.used_temp_tokens_id_seq OWNED BY public.used_temp_tokens.id;


--
-- Name: user_preferences; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_preferences (
    id integer NOT NULL,
    uuid character varying(36) NOT NULL,
    user_id integer NOT NULL,
    tenant_id integer NOT NULL,
    ui_preferences json NOT NULL,
    ai_preferences json NOT NULL,
    learning_preferences json NOT NULL,
    privacy_preferences json NOT NULL,
    notification_preferences json NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: user_preferences_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_preferences_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_preferences_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_preferences_id_seq OWNED BY public.user_preferences.id;


--
-- Name: user_progress; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_progress (
    id integer NOT NULL,
    uuid character varying(36) NOT NULL,
    user_id integer NOT NULL,
    tenant_id integer NOT NULL,
    resource_id integer NOT NULL,
    skill_area character varying(50) NOT NULL,
    current_level character varying(20) NOT NULL,
    experience_points integer NOT NULL,
    completion_percentage double precision NOT NULL,
    total_sessions integer NOT NULL,
    total_time_minutes integer NOT NULL,
    success_rate double precision NOT NULL,
    average_score double precision NOT NULL,
    achievements json NOT NULL,
    milestones json NOT NULL,
    learning_analytics json NOT NULL,
    difficulty_adjustments json NOT NULL,
    strength_areas json NOT NULL,
    improvement_areas json NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    last_activity timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: user_progress_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_progress_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_progress_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_progress_id_seq OWNED BY public.user_progress.id;


--
-- Name: user_resource_data; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_resource_data (
    id integer NOT NULL,
    uuid character varying(36) NOT NULL,
    user_id integer NOT NULL,
    tenant_id integer NOT NULL,
    resource_id integer NOT NULL,
    data_type character varying(50) NOT NULL,
    data_key character varying(100) NOT NULL,
    data_value json NOT NULL,
    is_encrypted boolean NOT NULL,
    expiry_date timestamp with time zone,
    version integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    accessed_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: user_resource_data_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_resource_data_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_resource_data_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_resource_data_id_seq OWNED BY public.user_resource_data.id;


--
-- Name: user_tenant_assignments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_tenant_assignments (
    id integer NOT NULL,
    user_id integer NOT NULL,
    tenant_id integer NOT NULL,
    tenant_user_role character varying(20) NOT NULL,
    tenant_display_name character varying(100),
    tenant_email character varying(255),
    tenant_department character varying(100),
    tenant_title character varying(100),
    tenant_password_hash character varying(255),
    requires_2fa boolean NOT NULL,
    last_password_change timestamp with time zone,
    tenant_capabilities json NOT NULL,
    resource_limits json NOT NULL,
    is_active boolean NOT NULL,
    is_primary_tenant boolean NOT NULL,
    joined_at timestamp with time zone DEFAULT now() NOT NULL,
    last_accessed timestamp with time zone,
    last_login_at timestamp with time zone,
    invited_by integer,
    invitation_accepted_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: user_tenant_assignments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_tenant_assignments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_tenant_assignments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_tenant_assignments_id_seq OWNED BY public.user_tenant_assignments.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id integer NOT NULL,
    uuid character varying(36) NOT NULL,
    email character varying(255) NOT NULL,
    full_name character varying(100) NOT NULL,
    hashed_password character varying(255) NOT NULL,
    user_type character varying(20) NOT NULL,
    tenant_id integer,
    current_tenant_id integer,
    capabilities json NOT NULL,
    is_active boolean NOT NULL,
    last_login timestamp with time zone,
    last_login_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    tfa_enabled boolean DEFAULT false NOT NULL,
    tfa_secret text,
    tfa_required boolean DEFAULT false NOT NULL
);


--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: ai_resources id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_resources ALTER COLUMN id SET DEFAULT nextval('public.ai_resources_id_seq'::regclass);


--
-- Name: audit_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs ALTER COLUMN id SET DEFAULT nextval('public.audit_logs_id_seq'::regclass);


--
-- Name: billing_plans id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.billing_plans ALTER COLUMN id SET DEFAULT nextval('public.billing_plans_id_seq'::regclass);


--
-- Name: billing_usage id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.billing_usage ALTER COLUMN id SET DEFAULT nextval('public.billing_usage_id_seq'::regclass);


--
-- Name: license_billing_usage id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.license_billing_usage ALTER COLUMN id SET DEFAULT nextval('public.license_billing_usage_id_seq'::regclass);


--
-- Name: license_seats id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.license_seats ALTER COLUMN id SET DEFAULT nextval('public.license_seats_id_seq'::regclass);


--
-- Name: licenses id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.licenses ALTER COLUMN id SET DEFAULT nextval('public.licenses_id_seq'::regclass);


--
-- Name: model_usage_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_usage_logs ALTER COLUMN id SET DEFAULT nextval('public.model_usage_logs_id_seq'::regclass);


--
-- Name: password_reset_rate_limits id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.password_reset_rate_limits ALTER COLUMN id SET DEFAULT nextval('public.password_reset_rate_limits_id_seq'::regclass);


--
-- Name: resource_alerts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resource_alerts ALTER COLUMN id SET DEFAULT nextval('public.resource_alerts_id_seq'::regclass);


--
-- Name: resource_pricing id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resource_pricing ALTER COLUMN id SET DEFAULT nextval('public.resource_pricing_id_seq'::regclass);


--
-- Name: resource_quotas id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resource_quotas ALTER COLUMN id SET DEFAULT nextval('public.resource_quotas_id_seq'::regclass);


--
-- Name: resource_templates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resource_templates ALTER COLUMN id SET DEFAULT nextval('public.resource_templates_id_seq'::regclass);


--
-- Name: resource_usage id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resource_usage ALTER COLUMN id SET DEFAULT nextval('public.resource_usage_id_seq'::regclass);


--
-- Name: session_data id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.session_data ALTER COLUMN id SET DEFAULT nextval('public.session_data_id_seq'::regclass);


--
-- Name: system_metrics id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.system_metrics ALTER COLUMN id SET DEFAULT nextval('public.system_metrics_id_seq'::regclass);


--
-- Name: tenant_model_configs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_model_configs ALTER COLUMN id SET DEFAULT nextval('public.tenant_model_configs_id_seq'::regclass);


--
-- Name: tenant_resources id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_resources ALTER COLUMN id SET DEFAULT nextval('public.tenant_resources_id_seq'::regclass);


--
-- Name: tenant_templates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_templates ALTER COLUMN id SET DEFAULT nextval('public.tenant_templates_id_seq'::regclass);


--
-- Name: tenants id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenants ALTER COLUMN id SET DEFAULT nextval('public.tenants_id_seq'::regclass);


--
-- Name: tfa_verification_rate_limits id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tfa_verification_rate_limits ALTER COLUMN id SET DEFAULT nextval('public.tfa_verification_rate_limits_id_seq'::regclass);


--
-- Name: usage_records id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usage_records ALTER COLUMN id SET DEFAULT nextval('public.usage_records_id_seq'::regclass);


--
-- Name: used_temp_tokens id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.used_temp_tokens ALTER COLUMN id SET DEFAULT nextval('public.used_temp_tokens_id_seq'::regclass);


--
-- Name: user_preferences id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_preferences ALTER COLUMN id SET DEFAULT nextval('public.user_preferences_id_seq'::regclass);


--
-- Name: user_progress id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_progress ALTER COLUMN id SET DEFAULT nextval('public.user_progress_id_seq'::regclass);


--
-- Name: user_resource_data id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_resource_data ALTER COLUMN id SET DEFAULT nextval('public.user_resource_data_id_seq'::regclass);


--
-- Name: user_tenant_assignments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_tenant_assignments ALTER COLUMN id SET DEFAULT nextval('public.user_tenant_assignments_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: api_keys api_keys_key_hash_key; Type: CONSTRAINT; Schema: admin_control; Owner: -
--

ALTER TABLE ONLY admin_control.api_keys
    ADD CONSTRAINT api_keys_key_hash_key UNIQUE (key_hash);


--
-- Name: api_keys api_keys_pkey; Type: CONSTRAINT; Schema: admin_control; Owner: -
--

ALTER TABLE ONLY admin_control.api_keys
    ADD CONSTRAINT api_keys_pkey PRIMARY KEY (id);


--
-- Name: model_registry model_registry_pkey; Type: CONSTRAINT; Schema: admin_control; Owner: -
--

ALTER TABLE ONLY admin_control.model_registry
    ADD CONSTRAINT model_registry_pkey PRIMARY KEY (id);


--
-- Name: model_registry model_registry_provider_model_id_key; Type: CONSTRAINT; Schema: admin_control; Owner: -
--

ALTER TABLE ONLY admin_control.model_registry
    ADD CONSTRAINT model_registry_provider_model_id_key UNIQUE (provider, model_id);


--
-- Name: system_config system_config_config_key_key; Type: CONSTRAINT; Schema: admin_control; Owner: -
--

ALTER TABLE ONLY admin_control.system_config
    ADD CONSTRAINT system_config_config_key_key UNIQUE (config_key);


--
-- Name: system_config system_config_pkey; Type: CONSTRAINT; Schema: admin_control; Owner: -
--

ALTER TABLE ONLY admin_control.system_config
    ADD CONSTRAINT system_config_pkey PRIMARY KEY (id);


--
-- Name: system_metrics system_metrics_pkey; Type: CONSTRAINT; Schema: admin_control; Owner: -
--

ALTER TABLE ONLY admin_control.system_metrics
    ADD CONSTRAINT system_metrics_pkey PRIMARY KEY (id);


--
-- Name: tenants tenants_domain_key; Type: CONSTRAINT; Schema: admin_control; Owner: -
--

ALTER TABLE ONLY admin_control.tenants
    ADD CONSTRAINT tenants_domain_key UNIQUE (domain);


--
-- Name: tenants tenants_pkey; Type: CONSTRAINT; Schema: admin_control; Owner: -
--

ALTER TABLE ONLY admin_control.tenants
    ADD CONSTRAINT tenants_pkey PRIMARY KEY (id);


--
-- Name: ai_resources ai_resources_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_resources
    ADD CONSTRAINT ai_resources_pkey PRIMARY KEY (id);


--
-- Name: ai_resources ai_resources_uuid_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_resources
    ADD CONSTRAINT ai_resources_uuid_key UNIQUE (uuid);


--
-- Name: audit_logs audit_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_pkey PRIMARY KEY (id);


--
-- Name: billing_plans billing_plans_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.billing_plans
    ADD CONSTRAINT billing_plans_name_key UNIQUE (name);


--
-- Name: billing_plans billing_plans_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.billing_plans
    ADD CONSTRAINT billing_plans_pkey PRIMARY KEY (id);


--
-- Name: billing_usage billing_usage_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.billing_usage
    ADD CONSTRAINT billing_usage_pkey PRIMARY KEY (id);


--
-- Name: license_billing_usage license_billing_usage_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.license_billing_usage
    ADD CONSTRAINT license_billing_usage_pkey PRIMARY KEY (id);


--
-- Name: license_seats license_seats_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.license_seats
    ADD CONSTRAINT license_seats_pkey PRIMARY KEY (id);


--
-- Name: licenses licenses_license_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.licenses
    ADD CONSTRAINT licenses_license_key_key UNIQUE (license_key);


--
-- Name: licenses licenses_license_uuid_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.licenses
    ADD CONSTRAINT licenses_license_uuid_key UNIQUE (license_uuid);


--
-- Name: licenses licenses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.licenses
    ADD CONSTRAINT licenses_pkey PRIMARY KEY (id);


--
-- Name: licenses licenses_tenant_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.licenses
    ADD CONSTRAINT licenses_tenant_id_key UNIQUE (tenant_id);


--
-- Name: model_configs model_configs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_configs
    ADD CONSTRAINT model_configs_pkey PRIMARY KEY (model_id);


--
-- Name: model_usage_logs model_usage_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_usage_logs
    ADD CONSTRAINT model_usage_logs_pkey PRIMARY KEY (id);


--
-- Name: password_reset_rate_limits password_reset_rate_limits_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.password_reset_rate_limits
    ADD CONSTRAINT password_reset_rate_limits_pkey PRIMARY KEY (id);


--
-- Name: resource_alerts resource_alerts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resource_alerts
    ADD CONSTRAINT resource_alerts_pkey PRIMARY KEY (id);


--
-- Name: resource_pricing resource_pricing_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resource_pricing
    ADD CONSTRAINT resource_pricing_pkey PRIMARY KEY (id);


--
-- Name: resource_quotas resource_quotas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resource_quotas
    ADD CONSTRAINT resource_quotas_pkey PRIMARY KEY (id);


--
-- Name: resource_templates resource_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resource_templates
    ADD CONSTRAINT resource_templates_pkey PRIMARY KEY (id);


--
-- Name: resource_usage resource_usage_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resource_usage
    ADD CONSTRAINT resource_usage_pkey PRIMARY KEY (id);


--
-- Name: session_data session_data_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.session_data
    ADD CONSTRAINT session_data_pkey PRIMARY KEY (id);


--
-- Name: session_data session_data_uuid_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.session_data
    ADD CONSTRAINT session_data_uuid_key UNIQUE (uuid);


--
-- Name: system_metrics system_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.system_metrics
    ADD CONSTRAINT system_metrics_pkey PRIMARY KEY (id);


--
-- Name: tenant_model_configs tenant_model_configs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_model_configs
    ADD CONSTRAINT tenant_model_configs_pkey PRIMARY KEY (id);


--
-- Name: tenant_resources tenant_resources_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_resources
    ADD CONSTRAINT tenant_resources_pkey PRIMARY KEY (id);


--
-- Name: tenant_templates tenant_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_templates
    ADD CONSTRAINT tenant_templates_pkey PRIMARY KEY (id);


--
-- Name: tenants tenants_namespace_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenants
    ADD CONSTRAINT tenants_namespace_key UNIQUE (namespace);


--
-- Name: tenants tenants_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenants
    ADD CONSTRAINT tenants_pkey PRIMARY KEY (id);


--
-- Name: tenants tenants_subdomain_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenants
    ADD CONSTRAINT tenants_subdomain_key UNIQUE (subdomain);


--
-- Name: tenants tenants_uuid_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenants
    ADD CONSTRAINT tenants_uuid_key UNIQUE (uuid);


--
-- Name: tfa_verification_rate_limits tfa_verification_rate_limits_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tfa_verification_rate_limits
    ADD CONSTRAINT tfa_verification_rate_limits_pkey PRIMARY KEY (id);


--
-- Name: tenant_model_configs unique_tenant_model; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_model_configs
    ADD CONSTRAINT unique_tenant_model UNIQUE (tenant_id, model_id);


--
-- Name: tenant_resources unique_tenant_resource; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_resources
    ADD CONSTRAINT unique_tenant_resource UNIQUE (tenant_id, resource_id);


--
-- Name: user_tenant_assignments unique_user_tenant_assignment; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_tenant_assignments
    ADD CONSTRAINT unique_user_tenant_assignment UNIQUE (user_id, tenant_id);


--
-- Name: usage_records usage_records_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usage_records
    ADD CONSTRAINT usage_records_pkey PRIMARY KEY (id);


--
-- Name: used_temp_tokens used_temp_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.used_temp_tokens
    ADD CONSTRAINT used_temp_tokens_pkey PRIMARY KEY (id);


--
-- Name: used_temp_tokens used_temp_tokens_token_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.used_temp_tokens
    ADD CONSTRAINT used_temp_tokens_token_id_key UNIQUE (token_id);


--
-- Name: user_preferences user_preferences_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_preferences
    ADD CONSTRAINT user_preferences_pkey PRIMARY KEY (id);


--
-- Name: user_preferences user_preferences_uuid_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_preferences
    ADD CONSTRAINT user_preferences_uuid_key UNIQUE (uuid);


--
-- Name: user_progress user_progress_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_progress
    ADD CONSTRAINT user_progress_pkey PRIMARY KEY (id);


--
-- Name: user_progress user_progress_uuid_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_progress
    ADD CONSTRAINT user_progress_uuid_key UNIQUE (uuid);


--
-- Name: user_resource_data user_resource_data_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_resource_data
    ADD CONSTRAINT user_resource_data_pkey PRIMARY KEY (id);


--
-- Name: user_resource_data user_resource_data_uuid_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_resource_data
    ADD CONSTRAINT user_resource_data_uuid_key UNIQUE (uuid);


--
-- Name: user_tenant_assignments user_tenant_assignments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_tenant_assignments
    ADD CONSTRAINT user_tenant_assignments_pkey PRIMARY KEY (id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: users users_uuid_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_uuid_key UNIQUE (uuid);


--
-- Name: idx_api_keys_provider; Type: INDEX; Schema: admin_control; Owner: -
--

CREATE INDEX idx_api_keys_provider ON admin_control.api_keys USING btree (provider);


--
-- Name: idx_api_keys_status; Type: INDEX; Schema: admin_control; Owner: -
--

CREATE INDEX idx_api_keys_status ON admin_control.api_keys USING btree (status);


--
-- Name: idx_model_registry_provider; Type: INDEX; Schema: admin_control; Owner: -
--

CREATE INDEX idx_model_registry_provider ON admin_control.model_registry USING btree (provider);


--
-- Name: idx_model_registry_status; Type: INDEX; Schema: admin_control; Owner: -
--

CREATE INDEX idx_model_registry_status ON admin_control.model_registry USING btree (status);


--
-- Name: idx_system_config_key; Type: INDEX; Schema: admin_control; Owner: -
--

CREATE INDEX idx_system_config_key ON admin_control.system_config USING btree (config_key);


--
-- Name: idx_system_metrics_name_timestamp; Type: INDEX; Schema: admin_control; Owner: -
--

CREATE INDEX idx_system_metrics_name_timestamp ON admin_control.system_metrics USING btree (metric_name, "timestamp" DESC);


--
-- Name: idx_system_metrics_tenant_timestamp; Type: INDEX; Schema: admin_control; Owner: -
--

CREATE INDEX idx_system_metrics_tenant_timestamp ON admin_control.system_metrics USING btree (tenant_id, "timestamp" DESC);


--
-- Name: idx_tenants_domain; Type: INDEX; Schema: admin_control; Owner: -
--

CREATE INDEX idx_tenants_domain ON admin_control.tenants USING btree (domain);


--
-- Name: idx_tenants_status; Type: INDEX; Schema: admin_control; Owner: -
--

CREATE INDEX idx_tenants_status ON admin_control.tenants USING btree (status);


--
-- Name: ix_ai_resources_health_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_resources_health_status ON public.ai_resources USING btree (health_status);


--
-- Name: ix_ai_resources_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_resources_id ON public.ai_resources USING btree (id);


--
-- Name: ix_ai_resources_is_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_resources_is_active ON public.ai_resources USING btree (is_active);


--
-- Name: ix_ai_resources_personalization_mode; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_resources_personalization_mode ON public.ai_resources USING btree (personalization_mode);


--
-- Name: ix_ai_resources_provider; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_resources_provider ON public.ai_resources USING btree (provider);


--
-- Name: ix_ai_resources_resource_subtype; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_resources_resource_subtype ON public.ai_resources USING btree (resource_subtype);


--
-- Name: ix_ai_resources_resource_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_resources_resource_type ON public.ai_resources USING btree (resource_type);


--
-- Name: ix_audit_logs_action; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_logs_action ON public.audit_logs USING btree (action);


--
-- Name: ix_audit_logs_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_logs_created_at ON public.audit_logs USING btree (created_at);


--
-- Name: ix_audit_logs_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_logs_id ON public.audit_logs USING btree (id);


--
-- Name: ix_audit_logs_resource_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_logs_resource_type ON public.audit_logs USING btree (resource_type);


--
-- Name: ix_audit_logs_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_logs_tenant_id ON public.audit_logs USING btree (tenant_id);


--
-- Name: ix_audit_logs_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_logs_user_id ON public.audit_logs USING btree (user_id);


--
-- Name: ix_billing_plans_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_billing_plans_id ON public.billing_plans USING btree (id);


--
-- Name: ix_billing_usage_billing_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_billing_usage_billing_date ON public.billing_usage USING btree (billing_date);


--
-- Name: ix_billing_usage_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_billing_usage_id ON public.billing_usage USING btree (id);


--
-- Name: ix_billing_usage_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_billing_usage_tenant_id ON public.billing_usage USING btree (tenant_id);


--
-- Name: ix_license_billing_usage_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_license_billing_usage_id ON public.license_billing_usage USING btree (id);


--
-- Name: ix_license_seats_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_license_seats_id ON public.license_seats USING btree (id);


--
-- Name: ix_licenses_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_licenses_id ON public.licenses USING btree (id);


--
-- Name: ix_model_usage_logs_model_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_model_usage_logs_model_id ON public.model_usage_logs USING btree (model_id);


--
-- Name: ix_model_usage_logs_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_model_usage_logs_tenant_id ON public.model_usage_logs USING btree (tenant_id);


--
-- Name: ix_password_reset_rate_limits_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_password_reset_rate_limits_email ON public.password_reset_rate_limits USING btree (email);


--
-- Name: ix_password_reset_rate_limits_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_password_reset_rate_limits_id ON public.password_reset_rate_limits USING btree (id);


--
-- Name: ix_password_reset_rate_limits_window_end; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_password_reset_rate_limits_window_end ON public.password_reset_rate_limits USING btree (window_end);


--
-- Name: ix_resource_alerts_alert_level; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_resource_alerts_alert_level ON public.resource_alerts USING btree (alert_level);


--
-- Name: ix_resource_alerts_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_resource_alerts_created_at ON public.resource_alerts USING btree (created_at);


--
-- Name: ix_resource_alerts_resource_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_resource_alerts_resource_type ON public.resource_alerts USING btree (resource_type);


--
-- Name: ix_resource_alerts_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_resource_alerts_tenant_id ON public.resource_alerts USING btree (tenant_id);


--
-- Name: ix_resource_pricing_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_resource_pricing_id ON public.resource_pricing USING btree (id);


--
-- Name: ix_resource_quotas_resource_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_resource_quotas_resource_type ON public.resource_quotas USING btree (resource_type);


--
-- Name: ix_resource_quotas_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_resource_quotas_tenant_id ON public.resource_quotas USING btree (tenant_id);


--
-- Name: ix_resource_templates_name; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_resource_templates_name ON public.resource_templates USING btree (name);


--
-- Name: ix_resource_usage_resource_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_resource_usage_resource_type ON public.resource_usage USING btree (resource_type);


--
-- Name: ix_resource_usage_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_resource_usage_tenant_id ON public.resource_usage USING btree (tenant_id);


--
-- Name: ix_resource_usage_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_resource_usage_timestamp ON public.resource_usage USING btree ("timestamp");


--
-- Name: ix_session_data_data_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_session_data_data_type ON public.session_data USING btree (data_type);


--
-- Name: ix_session_data_expires_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_session_data_expires_at ON public.session_data USING btree (expires_at);


--
-- Name: ix_session_data_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_session_data_id ON public.session_data USING btree (id);


--
-- Name: ix_session_data_resource_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_session_data_resource_id ON public.session_data USING btree (resource_id);


--
-- Name: ix_session_data_session_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_session_data_session_id ON public.session_data USING btree (session_id);


--
-- Name: ix_session_data_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_session_data_tenant_id ON public.session_data USING btree (tenant_id);


--
-- Name: ix_session_data_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_session_data_user_id ON public.session_data USING btree (user_id);


--
-- Name: ix_system_metrics_metric_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_system_metrics_metric_name ON public.system_metrics USING btree (metric_name);


--
-- Name: ix_system_metrics_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_system_metrics_timestamp ON public.system_metrics USING btree ("timestamp");


--
-- Name: ix_tenant_model_configs_model_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tenant_model_configs_model_id ON public.tenant_model_configs USING btree (model_id);


--
-- Name: ix_tenant_model_configs_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tenant_model_configs_tenant_id ON public.tenant_model_configs USING btree (tenant_id);


--
-- Name: ix_tenant_resources_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tenant_resources_id ON public.tenant_resources USING btree (id);


--
-- Name: ix_tenant_templates_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tenant_templates_id ON public.tenant_templates USING btree (id);


--
-- Name: ix_tenant_templates_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tenant_templates_name ON public.tenant_templates USING btree (name);


--
-- Name: ix_tenants_domain; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_tenants_domain ON public.tenants USING btree (domain);


--
-- Name: ix_tenants_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tenants_id ON public.tenants USING btree (id);


--
-- Name: ix_tenants_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tenants_status ON public.tenants USING btree (status);


--
-- Name: ix_tfa_verification_rate_limits_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tfa_verification_rate_limits_user_id ON public.tfa_verification_rate_limits USING btree (user_id);


--
-- Name: ix_tfa_verification_rate_limits_window_end; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tfa_verification_rate_limits_window_end ON public.tfa_verification_rate_limits USING btree (window_end);


--
-- Name: ix_usage_records_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_usage_records_created_at ON public.usage_records USING btree (created_at);


--
-- Name: ix_usage_records_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_usage_records_id ON public.usage_records USING btree (id);


--
-- Name: ix_usage_records_request_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_usage_records_request_type ON public.usage_records USING btree (request_type);


--
-- Name: ix_usage_records_resource_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_usage_records_resource_id ON public.usage_records USING btree (resource_id);


--
-- Name: ix_usage_records_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_usage_records_tenant_id ON public.usage_records USING btree (tenant_id);


--
-- Name: ix_usage_records_user_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_usage_records_user_email ON public.usage_records USING btree (user_email);


--
-- Name: ix_used_temp_tokens_expires_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_used_temp_tokens_expires_at ON public.used_temp_tokens USING btree (expires_at);


--
-- Name: ix_used_temp_tokens_token_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_used_temp_tokens_token_id ON public.used_temp_tokens USING btree (token_id);


--
-- Name: ix_user_preferences_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_preferences_id ON public.user_preferences USING btree (id);


--
-- Name: ix_user_preferences_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_preferences_tenant_id ON public.user_preferences USING btree (tenant_id);


--
-- Name: ix_user_preferences_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_preferences_user_id ON public.user_preferences USING btree (user_id);


--
-- Name: ix_user_progress_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_progress_id ON public.user_progress USING btree (id);


--
-- Name: ix_user_progress_resource_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_progress_resource_id ON public.user_progress USING btree (resource_id);


--
-- Name: ix_user_progress_skill_area; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_progress_skill_area ON public.user_progress USING btree (skill_area);


--
-- Name: ix_user_progress_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_progress_tenant_id ON public.user_progress USING btree (tenant_id);


--
-- Name: ix_user_progress_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_progress_user_id ON public.user_progress USING btree (user_id);


--
-- Name: ix_user_resource_data_data_key; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_resource_data_data_key ON public.user_resource_data USING btree (data_key);


--
-- Name: ix_user_resource_data_data_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_resource_data_data_type ON public.user_resource_data USING btree (data_type);


--
-- Name: ix_user_resource_data_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_resource_data_id ON public.user_resource_data USING btree (id);


--
-- Name: ix_user_resource_data_resource_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_resource_data_resource_id ON public.user_resource_data USING btree (resource_id);


--
-- Name: ix_user_resource_data_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_resource_data_tenant_id ON public.user_resource_data USING btree (tenant_id);


--
-- Name: ix_user_resource_data_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_resource_data_user_id ON public.user_resource_data USING btree (user_id);


--
-- Name: ix_user_tenant_assignments_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_tenant_assignments_id ON public.user_tenant_assignments USING btree (id);


--
-- Name: ix_user_tenant_assignments_tenant_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_tenant_assignments_tenant_email ON public.user_tenant_assignments USING btree (tenant_email);


--
-- Name: ix_user_tenant_assignments_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_tenant_assignments_tenant_id ON public.user_tenant_assignments USING btree (tenant_id);


--
-- Name: ix_user_tenant_assignments_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_tenant_assignments_user_id ON public.user_tenant_assignments USING btree (user_id);


--
-- Name: ix_users_current_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_current_tenant_id ON public.users USING btree (current_tenant_id);


--
-- Name: ix_users_email; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);


--
-- Name: ix_users_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_id ON public.users USING btree (id);


--
-- Name: ix_users_tfa_enabled; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_tfa_enabled ON public.users USING btree (tfa_enabled);


--
-- Name: ix_users_tfa_required; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_tfa_required ON public.users USING btree (tfa_required);


--
-- Name: system_metrics system_metrics_tenant_id_fkey; Type: FK CONSTRAINT; Schema: admin_control; Owner: -
--

ALTER TABLE ONLY admin_control.system_metrics
    ADD CONSTRAINT system_metrics_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES admin_control.tenants(id);


--
-- Name: audit_logs audit_logs_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE SET NULL;


--
-- Name: audit_logs audit_logs_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: billing_usage billing_usage_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.billing_usage
    ADD CONSTRAINT billing_usage_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);


--
-- Name: license_billing_usage license_billing_usage_license_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.license_billing_usage
    ADD CONSTRAINT license_billing_usage_license_id_fkey FOREIGN KEY (license_id) REFERENCES public.licenses(id);


--
-- Name: license_billing_usage license_billing_usage_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.license_billing_usage
    ADD CONSTRAINT license_billing_usage_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);


--
-- Name: license_seats license_seats_license_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.license_seats
    ADD CONSTRAINT license_seats_license_id_fkey FOREIGN KEY (license_id) REFERENCES public.licenses(id);


--
-- Name: license_seats license_seats_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.license_seats
    ADD CONSTRAINT license_seats_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: licenses licenses_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.licenses
    ADD CONSTRAINT licenses_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);


--
-- Name: resource_alerts resource_alerts_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resource_alerts
    ADD CONSTRAINT resource_alerts_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: resource_pricing resource_pricing_resource_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resource_pricing
    ADD CONSTRAINT resource_pricing_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.ai_resources(id);


--
-- Name: resource_quotas resource_quotas_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resource_quotas
    ADD CONSTRAINT resource_quotas_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: resource_usage resource_usage_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resource_usage
    ADD CONSTRAINT resource_usage_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: session_data session_data_resource_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.session_data
    ADD CONSTRAINT session_data_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.ai_resources(id) ON DELETE CASCADE;


--
-- Name: session_data session_data_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.session_data
    ADD CONSTRAINT session_data_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: session_data session_data_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.session_data
    ADD CONSTRAINT session_data_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: tenant_model_configs tenant_model_configs_model_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_model_configs
    ADD CONSTRAINT tenant_model_configs_model_id_fkey FOREIGN KEY (model_id) REFERENCES public.model_configs(model_id) ON DELETE CASCADE;


--
-- Name: tenant_model_configs tenant_model_configs_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_model_configs
    ADD CONSTRAINT tenant_model_configs_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: tenant_resources tenant_resources_resource_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_resources
    ADD CONSTRAINT tenant_resources_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.ai_resources(id) ON DELETE CASCADE;


--
-- Name: tenant_resources tenant_resources_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_resources
    ADD CONSTRAINT tenant_resources_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: tfa_verification_rate_limits tfa_verification_rate_limits_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tfa_verification_rate_limits
    ADD CONSTRAINT tfa_verification_rate_limits_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: usage_records usage_records_resource_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usage_records
    ADD CONSTRAINT usage_records_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.ai_resources(id) ON DELETE CASCADE;


--
-- Name: usage_records usage_records_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usage_records
    ADD CONSTRAINT usage_records_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: used_temp_tokens used_temp_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.used_temp_tokens
    ADD CONSTRAINT used_temp_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_preferences user_preferences_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_preferences
    ADD CONSTRAINT user_preferences_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: user_preferences user_preferences_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_preferences
    ADD CONSTRAINT user_preferences_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_progress user_progress_resource_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_progress
    ADD CONSTRAINT user_progress_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.ai_resources(id) ON DELETE CASCADE;


--
-- Name: user_progress user_progress_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_progress
    ADD CONSTRAINT user_progress_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: user_progress user_progress_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_progress
    ADD CONSTRAINT user_progress_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_resource_data user_resource_data_resource_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_resource_data
    ADD CONSTRAINT user_resource_data_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.ai_resources(id) ON DELETE CASCADE;


--
-- Name: user_resource_data user_resource_data_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_resource_data
    ADD CONSTRAINT user_resource_data_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: user_resource_data user_resource_data_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_resource_data
    ADD CONSTRAINT user_resource_data_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_tenant_assignments user_tenant_assignments_invited_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_tenant_assignments
    ADD CONSTRAINT user_tenant_assignments_invited_by_fkey FOREIGN KEY (invited_by) REFERENCES public.users(id);


--
-- Name: user_tenant_assignments user_tenant_assignments_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_tenant_assignments
    ADD CONSTRAINT user_tenant_assignments_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: user_tenant_assignments user_tenant_assignments_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_tenant_assignments
    ADD CONSTRAINT user_tenant_assignments_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: users users_current_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_current_tenant_id_fkey FOREIGN KEY (current_tenant_id) REFERENCES public.tenants(id);


--
-- Name: users users_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

