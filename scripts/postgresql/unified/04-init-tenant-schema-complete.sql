--
-- PostgreSQL database dump
--

-- NOTE: Removed \c gt2_tenants - Docker entrypoint runs this script
-- against POSTGRES_DB (gt2_tenants) automatically. The \c command
-- doesn't work reliably in entrypoint context.

-- Dumped from database version 15.14 (Debian 15.14-1.pgdg12+1)
-- Dumped by pg_dump version 15.14 (Debian 15.14-1.pgdg12+1)

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
-- Name: tenant_test_company; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA tenant_test_company;


--
-- Name: auto_unshare_on_permission_downgrade(); Type: FUNCTION; Schema: tenant_test_company; Owner: -
--

CREATE FUNCTION tenant_test_company.auto_unshare_on_permission_downgrade() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- Clear resource_permissions when downgrading from share/manager to read
    -- Manager and Contributor (share) can share resources
    -- Member (read) cannot share resources
    IF OLD.team_permission IN ('share', 'manager')
       AND NEW.team_permission = 'read' THEN
        NEW.resource_permissions := '{}'::jsonb;
    END IF;

    RETURN NEW;
END;
$$;


--
-- Name: FUNCTION auto_unshare_on_permission_downgrade(); Type: COMMENT; Schema: tenant_test_company; Owner: -
--

COMMENT ON FUNCTION tenant_test_company.auto_unshare_on_permission_downgrade() IS 'Clears resource_permissions when member is downgraded to read-only (Member role)';


--
-- Name: check_user_resource_permission(uuid, character varying, uuid, character varying); Type: FUNCTION; Schema: tenant_test_company; Owner: -
--

CREATE FUNCTION tenant_test_company.check_user_resource_permission(p_user_id uuid, p_resource_type character varying, p_resource_id uuid, p_required_permission character varying DEFAULT 'read'::character varying) RETURNS boolean
    LANGUAGE plpgsql
    AS $$
DECLARE
    user_permission VARCHAR;
BEGIN
    -- Get the user's permission from any team that has this resource
    SELECT (ura.permission::text)
    INTO user_permission
    FROM user_resource_access ura
    WHERE ura.user_id = p_user_id
      AND ura.resource_type = p_resource_type
      AND ura.resource_id = p_resource_id
    LIMIT 1;

    -- If no permission found, return false
    IF user_permission IS NULL THEN
        RETURN FALSE;
    END IF;

    -- Remove quotes from JSONB string value
    user_permission := TRIM(BOTH '"' FROM user_permission);

    -- Check permission level
    IF p_required_permission = 'read' THEN
        RETURN user_permission IN ('read', 'edit');
    ELSIF p_required_permission = 'edit' THEN
        RETURN user_permission = 'edit';
    ELSE
        RETURN FALSE;
    END IF;
END;
$$;


--
-- Name: FUNCTION check_user_resource_permission(p_user_id uuid, p_resource_type character varying, p_resource_id uuid, p_required_permission character varying); Type: COMMENT; Schema: tenant_test_company; Owner: -
--

COMMENT ON FUNCTION tenant_test_company.check_user_resource_permission(p_user_id uuid, p_resource_type character varying, p_resource_id uuid, p_required_permission character varying) IS 'Check if user has required permission (read/edit) on a resource';


--
-- Name: cleanup_resource_permissions(); Type: FUNCTION; Schema: tenant_test_company; Owner: -
--

CREATE FUNCTION tenant_test_company.cleanup_resource_permissions() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- Remove the resource permission key from all team members
    UPDATE team_memberships
    SET resource_permissions = resource_permissions - (OLD.resource_type || ':' || OLD.resource_id::text)
    WHERE team_id = OLD.team_id
      AND resource_permissions ? (OLD.resource_type || ':' || OLD.resource_id::text);

    RETURN OLD;
END;
$$;


--
-- Name: FUNCTION cleanup_resource_permissions(); Type: COMMENT; Schema: tenant_test_company; Owner: -
--

COMMENT ON FUNCTION tenant_test_company.cleanup_resource_permissions() IS 'Removes resource permission entries from team members when resource is unshared';


--
-- Name: get_observable_members(uuid); Type: FUNCTION; Schema: tenant_test_company; Owner: -
--

CREATE FUNCTION tenant_test_company.get_observable_members(p_team_id uuid) RETURNS TABLE(user_id uuid, user_email text, user_name text, observable_since timestamp with time zone)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT
        tm.user_id,
        u.email::text as user_email,
        u.full_name::text as user_name,
        tm.observable_consent_at
    FROM team_memberships tm
    JOIN users u ON tm.user_id = u.id
    WHERE tm.team_id = p_team_id
      AND tm.is_observable = true
      AND tm.observable_consent_status = 'approved'
      AND tm.status = 'accepted'
    ORDER BY tm.observable_consent_at DESC;
END;
$$;


--
-- Name: FUNCTION get_observable_members(p_team_id uuid); Type: COMMENT; Schema: tenant_test_company; Owner: -
--

COMMENT ON FUNCTION tenant_test_company.get_observable_members(p_team_id uuid) IS 'Returns list of Observable team members with approved consent status';


--
-- Name: get_team_resources(uuid, character varying); Type: FUNCTION; Schema: tenant_test_company; Owner: -
--

CREATE FUNCTION tenant_test_company.get_team_resources(p_team_id uuid, p_resource_type character varying DEFAULT NULL::character varying) RETURNS TABLE(resource_id uuid, resource_type character varying, shared_by uuid, created_at timestamp without time zone, member_count bigint)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT
        trs.resource_id,
        trs.resource_type,
        trs.shared_by,
        trs.created_at,
        COUNT(DISTINCT tm.user_id) as member_count
    FROM team_resource_shares trs
    JOIN team_memberships tm ON tm.team_id = trs.team_id
    WHERE trs.team_id = p_team_id
      AND (p_resource_type IS NULL OR trs.resource_type = p_resource_type)
      AND tm.resource_permissions ? (trs.resource_type || ':' || trs.resource_id::text)
    GROUP BY trs.resource_id, trs.resource_type, trs.shared_by, trs.created_at
    ORDER BY trs.created_at DESC;
END;
$$;


--
-- Name: FUNCTION get_team_resources(p_team_id uuid, p_resource_type character varying); Type: COMMENT; Schema: tenant_test_company; Owner: -
--

COMMENT ON FUNCTION tenant_test_company.get_team_resources(p_team_id uuid, p_resource_type character varying) IS 'Get all resources shared with a team, optionally filtered by resource type';


--
-- Name: hybrid_search_chunks(text, public.vector, uuid, uuid, uuid, integer, numeric, numeric, numeric); Type: FUNCTION; Schema: tenant_test_company; Owner: -
--

CREATE FUNCTION tenant_test_company.hybrid_search_chunks(p_query_text text, p_query_embedding public.vector, p_team_id uuid, p_user_id uuid, p_dataset_id uuid DEFAULT NULL::uuid, p_limit integer DEFAULT 10, p_similarity_threshold numeric DEFAULT 0.3, p_text_weight numeric DEFAULT 0.3, p_vector_weight numeric DEFAULT 0.7) RETURNS TABLE(id uuid, document_id uuid, content text, similarity_score numeric, text_rank numeric, combined_score numeric, metadata jsonb)
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
BEGIN
    RETURN QUERY
    WITH vector_search AS (
        SELECT 
            dc.id,
            dc.document_id,
            dc.content,
            1 - (dc.embedding <=> p_query_embedding) as similarity_score,
            dc.metadata
        FROM document_chunks dc
        WHERE dc.team_id = p_team_id
          AND (p_dataset_id IS NULL OR dc.dataset_id = p_dataset_id)
          AND dc.embedding IS NOT NULL
          AND 1 - (dc.embedding <=> p_query_embedding) > p_similarity_threshold
    ),
    text_search AS (
        SELECT 
            dc.id,
            dc.document_id,
            dc.content,
            ts_rank(to_tsvector('english', dc.content), plainto_tsquery('english', p_query_text)) as text_rank,
            dc.metadata
        FROM document_chunks dc
        WHERE dc.team_id = p_team_id
          AND (p_dataset_id IS NULL OR dc.dataset_id = p_dataset_id)
          AND to_tsvector('english', dc.content) @@ plainto_tsquery('english', p_query_text)
    )
    SELECT 
        COALESCE(vs.id, ts.id) as id,
        COALESCE(vs.document_id, ts.document_id) as document_id,
        COALESCE(vs.content, ts.content) as content,
        COALESCE(vs.similarity_score, 0) as similarity_score,
        COALESCE(ts.text_rank, 0) as text_rank,
        (COALESCE(vs.similarity_score, 0) * p_vector_weight + COALESCE(ts.text_rank, 0) * p_text_weight) as combined_score,
        COALESCE(vs.metadata, ts.metadata) as metadata
    FROM vector_search vs
    FULL OUTER JOIN text_search ts ON vs.id = ts.id
    ORDER BY combined_score DESC
    LIMIT p_limit;
END;
$$;


--
-- Name: search_conversation_history(uuid, text, uuid[], integer, integer); Type: FUNCTION; Schema: tenant_test_company; Owner: -
--

CREATE FUNCTION tenant_test_company.search_conversation_history(p_user_id uuid, p_query text, p_agent_filter uuid[] DEFAULT NULL::uuid[], p_days_back integer DEFAULT 30, p_limit integer DEFAULT 10) RETURNS TABLE(conversation_id uuid, message_id uuid, content text, role character varying, created_at timestamp with time zone, conversation_title character varying, agent_name character varying, relevance_score real)
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
BEGIN
    RETURN QUERY
    SELECT
        f.conversation_id,
        f.message_id,
        f.content,
        f.role,
        f.created_at,
        f.conversation_title,
        f.agent_name,
        f.relevance_score
    FROM search_conversation_history_with_fallbacks(
        p_user_id,
        p_query,
        p_agent_filter,
        p_days_back,
        p_limit
    ) f;
END;
$$;


--
-- Name: search_conversation_history_with_fallbacks(uuid, text, uuid[], integer, integer); Type: FUNCTION; Schema: tenant_test_company; Owner: -
--

CREATE FUNCTION tenant_test_company.search_conversation_history_with_fallbacks(p_user_id uuid, p_query text, p_agent_filter uuid[] DEFAULT NULL::uuid[], p_days_back integer DEFAULT 30, p_limit integer DEFAULT 10) RETURNS TABLE(conversation_id uuid, message_id uuid, content text, role character varying, created_at timestamp with time zone, conversation_title character varying, agent_name character varying, relevance_score real, search_method text)
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
DECLARE
    keyword_results_count INT := 0;
    generic_query_words TEXT[] := ARRAY['discuss', 'talk', 'conversation', 'previously', 'before', 'earlier', 'history', 'past', 'last', 'recent', 'what', 'did', 'we'];
    is_generic_query BOOLEAN := FALSE;
    query_word_count INT := 0;
BEGIN
    -- Analyze query to determine if it's generic
    SELECT COUNT(*) INTO query_word_count
    FROM unnest(string_to_array(lower(trim(p_query)), ' ')) word
    WHERE length(word) > 2;

    SELECT COUNT(*) > 0 INTO is_generic_query
    FROM unnest(string_to_array(lower(trim(p_query)), ' ')) word
    WHERE word = ANY(generic_query_words);

    -- Try keyword search first for specific queries
    IF NOT is_generic_query AND length(trim(p_query)) > 2 AND p_query <> '*' AND query_word_count > 0 THEN
        -- Enhanced keyword search
        RETURN QUERY
        SELECT
            m.conversation_id,
            m.id as message_id,
            m.content,
            m.role,
            m.created_at,
            c.title as conversation_title,
            a.name as agent_name,
            (
                ts_rank_cd(to_tsvector('english', m.content), plainto_tsquery('english', p_query))::real *
                (1.0 + LOG(GREATEST(LENGTH(m.content), 1)::real / 100.0))::real *
                CASE
                    WHEN m.created_at > NOW() - '2 hours'::INTERVAL THEN 0.1::real
                    WHEN m.created_at > NOW() - '24 hours'::INTERVAL THEN 0.7::real
                    ELSE 1.0::real
                END *
                CASE
                    WHEN m.role = 'user' THEN 1.2::real
                    WHEN m.role = 'agent' AND LENGTH(m.content) > 1000 THEN 1.1::real
                    WHEN m.role = 'agent' AND m.content ILIKE '%no conversation%' THEN 0.1::real
                    ELSE 1.0::real
                END
            )::real as relevance_score,
            'keyword'::TEXT as search_method
        FROM tenant_test_company.messages m
        JOIN tenant_test_company.conversations c ON c.id = m.conversation_id
        LEFT JOIN tenant_test_company.agents a ON a.id = c.agent_id
        WHERE
            m.user_id = p_user_id
            AND m.created_at >= NOW() - (p_days_back || ' days')::INTERVAL
            AND (p_agent_filter IS NULL OR c.agent_id = ANY(p_agent_filter))
            AND to_tsvector('english', m.content) @@ plainto_tsquery('english', p_query)
            AND m.role IN ('user', 'agent')
            AND LENGTH(m.content) >= 50
            AND NOT (
                m.content ILIKE '%search confirms there are no%' OR
                m.content ILIKE '%no previous conversations stored%' OR
                m.content ILIKE '%first interaction%' OR
                m.content ILIKE '%technical limitation%'
            )
        ORDER BY relevance_score DESC, LENGTH(m.content) DESC, m.created_at DESC
        LIMIT p_limit;

        GET DIAGNOSTICS keyword_results_count = ROW_COUNT;
        IF keyword_results_count > 0 THEN
            RETURN;
        END IF;
    END IF;

    -- Fallback: Recent substantial conversations (works for generic queries)
    RETURN QUERY
    SELECT
        m.conversation_id,
        m.id as message_id,
        m.content,
        m.role,
        m.created_at,
        c.title as conversation_title,
        a.name as agent_name,
        (
            CASE
                WHEN m.created_at > NOW() - '1 day'::INTERVAL THEN 1.0::real
                WHEN m.created_at > NOW() - '7 days'::INTERVAL THEN 0.8::real
                ELSE 0.6::real
            END *
            (1.0 + LOG(GREATEST(LENGTH(m.content), 1)::real / 200.0))::real *
            CASE
                WHEN m.role = 'user' THEN 1.1::real
                ELSE 1.0::real
            END
        )::real as relevance_score,
        'recent'::TEXT as search_method
    FROM tenant_test_company.messages m
    JOIN tenant_test_company.conversations c ON c.id = m.conversation_id
    LEFT JOIN tenant_test_company.agents a ON a.id = c.agent_id
    WHERE
        m.user_id = p_user_id
        AND m.created_at >= NOW() - (p_days_back || ' days')::INTERVAL
        AND (p_agent_filter IS NULL OR c.agent_id = ANY(p_agent_filter))
        AND m.role IN ('user', 'agent')
        AND LENGTH(m.content) >= 100  -- Substantial messages only
        AND NOT (
            m.content ILIKE '%search confirms there are no%' OR
            m.content ILIKE '%no previous conversations stored%' OR
            m.content ILIKE '%first interaction%' OR
            m.content ILIKE '%technical limitation%' OR
            m.content ILIKE '%conversation search functionality%'
        )
    ORDER BY relevance_score DESC, m.created_at DESC
    LIMIT p_limit;
END;
$$;


--
-- Name: update_subagent_updated_at(); Type: FUNCTION; Schema: tenant_test_company; Owner: -
--

CREATE FUNCTION tenant_test_company.update_subagent_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
            BEGIN
                NEW.updated_at = NOW();
                RETURN NEW;
            END;
            $$;


--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: tenant_test_company; Owner: -
--

CREATE FUNCTION tenant_test_company.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


--
-- Name: validate_resource_share(); Type: FUNCTION; Schema: tenant_test_company; Owner: -
--

CREATE FUNCTION tenant_test_company.validate_resource_share() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    user_team_permission VARCHAR(20);
    is_team_owner BOOLEAN;
    user_role VARCHAR(50);
BEGIN
    -- Get user's team permission
    SELECT team_permission INTO user_team_permission
    FROM team_memberships
    WHERE team_id = NEW.team_id
      AND user_id = NEW.shared_by;

    -- Check if user is the team owner
    SELECT EXISTS (
        SELECT 1 FROM teams
        WHERE id = NEW.team_id AND owner_id = NEW.shared_by
    ) INTO is_team_owner;

    -- Get user's system role for admin bypass
    SELECT role INTO user_role
    FROM users
    WHERE id = NEW.shared_by;

    -- Allow if: owner, or has share/manager permission, or is admin/developer
    IF is_team_owner THEN
        RETURN NEW;
    END IF;

    IF user_role IN ('admin', 'developer') THEN
        RETURN NEW;
    END IF;

    IF user_team_permission IS NULL THEN
        RAISE EXCEPTION 'User % is not a member of team %', NEW.shared_by, NEW.team_id;
    END IF;

    IF user_team_permission NOT IN ('share', 'manager') THEN
        RAISE EXCEPTION 'User % does not have permission to share resources (current permission: %)',
            NEW.shared_by, user_team_permission;
    END IF;

    RETURN NEW;
END;
$$;


--
-- Name: FUNCTION validate_resource_share(); Type: COMMENT; Schema: tenant_test_company; Owner: -
--

COMMENT ON FUNCTION tenant_test_company.validate_resource_share() IS 'Validates that only owners, managers, contributors (share), or admins can share resources to teams';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: agent_datasets; Type: TABLE; Schema: tenant_test_company; Owner: -
--

CREATE TABLE tenant_test_company.agent_datasets (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    agent_id uuid NOT NULL,
    dataset_id uuid NOT NULL,
    relevance_threshold numeric(3,2) DEFAULT 0.7,
    max_chunks integer DEFAULT 5,
    priority_order integer DEFAULT 0,
    is_active boolean DEFAULT true,
    auto_include boolean DEFAULT true,
    search_count integer DEFAULT 0,
    chunks_retrieved_total integer DEFAULT 0,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    last_used_at timestamp with time zone,
    CONSTRAINT agent_datasets_max_chunks_check CHECK ((max_chunks > 0)),
    CONSTRAINT agent_datasets_relevance_threshold_check CHECK (((relevance_threshold >= 0.0) AND (relevance_threshold <= 1.0)))
);


--
-- Name: agent_messages; Type: TABLE; Schema: tenant_test_company; Owner: -
--

CREATE TABLE tenant_test_company.agent_messages (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    from_agent_id character varying(255),
    to_agent_id character varying(255),
    conversation_id uuid,
    execution_id character varying(255),
    message_type character varying(50) NOT NULL,
    content jsonb,
    processed boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT now(),
    CONSTRAINT message_type_check CHECK (((message_type)::text = ANY (ARRAY[('data'::character varying)::text, ('control'::character varying)::text, ('error'::character varying)::text, ('result'::character varying)::text, ('status'::character varying)::text])))
);


--
-- Name: TABLE agent_messages; Type: COMMENT; Schema: tenant_test_company; Owner: -
--

COMMENT ON TABLE tenant_test_company.agent_messages IS 'Inter-agent communication messages during orchestration';


--
-- Name: agents; Type: TABLE; Schema: tenant_test_company; Owner: -
--

CREATE TABLE tenant_test_company.agents (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    system_prompt text,
    tenant_id uuid NOT NULL,
    created_by uuid NOT NULL,
    model character varying(100) DEFAULT 'mixtral-8x7b-32768'::character varying,
    temperature numeric(3,2) DEFAULT 0.7,
    max_tokens integer DEFAULT 4096,
    visibility character varying(20) DEFAULT 'individual'::character varying,
    configuration jsonb DEFAULT '{}'::jsonb,
    is_active boolean DEFAULT true,
    access_group character varying(50) DEFAULT 'INDIVIDUAL'::character varying,
    team_members uuid[] DEFAULT '{}'::uuid[],
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    agent_type character varying(50) DEFAULT 'conversational'::character varying,
    disclaimer character varying(500),
    easy_prompts jsonb DEFAULT '[]'::jsonb,
    CONSTRAINT agents_access_group_check CHECK (((access_group)::text = ANY (ARRAY[('individual'::character varying)::text, ('team'::character varying)::text, ('organization'::character varying)::text]))),
    CONSTRAINT agents_max_tokens_check CHECK ((max_tokens > 0)),
    CONSTRAINT agents_temperature_check CHECK (((temperature >= 0.0) AND (temperature <= 2.0))),
    CONSTRAINT agents_visibility_check CHECK (((visibility)::text = ANY (ARRAY[('individual'::character varying)::text, ('team'::character varying)::text, ('organization'::character varying)::text])))
);


--
-- Name: conversation_datasets; Type: TABLE; Schema: tenant_test_company; Owner: -
--

CREATE TABLE tenant_test_company.conversation_datasets (
    conversation_id uuid NOT NULL,
    dataset_id uuid NOT NULL,
    attached_at timestamp with time zone DEFAULT now(),
    attached_by uuid NOT NULL,
    is_active boolean DEFAULT true
);


--
-- Name: conversation_settings; Type: TABLE; Schema: tenant_test_company; Owner: -
--

CREATE TABLE tenant_test_company.conversation_settings (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    conversation_id uuid NOT NULL,
    model_id character varying(255),
    temperature double precision DEFAULT 0.7,
    max_tokens integer DEFAULT 4096,
    system_prompt text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    rag_enabled boolean DEFAULT true,
    history_search_enabled boolean DEFAULT false,
    history_search_scope character varying(20) DEFAULT 'recent'::character varying,
    search_method character varying(20) DEFAULT 'auto'::character varying
);


--
-- Name: conversations; Type: TABLE; Schema: tenant_test_company; Owner: -
--

CREATE TABLE tenant_test_company.conversations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    title character varying(255) DEFAULT 'New Conversation'::character varying NOT NULL,
    tenant_id uuid NOT NULL,
    user_id uuid NOT NULL,
    agent_id uuid,
    summary text,
    total_messages integer DEFAULT 0,
    total_tokens integer DEFAULT 0,
    metadata jsonb DEFAULT '{}'::jsonb,
    is_archived boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: datasets; Type: TABLE; Schema: tenant_test_company; Owner: -
--

CREATE TABLE tenant_test_company.datasets (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    tenant_id uuid NOT NULL,
    created_by uuid NOT NULL,
    collection_name character varying(255) NOT NULL,
    document_count integer DEFAULT 0,
    total_size_bytes bigint DEFAULT 0,
    embedding_model character varying(100) DEFAULT 'BAAI/bge-m3'::character varying,
    visibility character varying(20) DEFAULT 'individual'::character varying,
    metadata jsonb DEFAULT '{}'::jsonb,
    is_active boolean DEFAULT true,
    access_group character varying(50) DEFAULT 'INDIVIDUAL'::character varying,
    team_members uuid[] DEFAULT '{}'::uuid[],
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    conversation_id uuid,
    search_method character varying(20) DEFAULT 'hybrid'::character varying,
    specialized_language boolean DEFAULT false,
    chunk_size integer DEFAULT 512,
    chunk_overlap integer DEFAULT 128,
    summary text,
    summary_generated_at timestamp without time zone,
    summary_model character varying(100) DEFAULT 'llama-3.1-8b-instant'::character varying,
    CONSTRAINT datasets_access_group_check CHECK (((access_group)::text = ANY (ARRAY[('individual'::character varying)::text, ('team'::character varying)::text, ('organization'::character varying)::text]))),
    CONSTRAINT datasets_chunk_overlap_check CHECK ((chunk_overlap >= 0)),
    CONSTRAINT datasets_chunk_size_check CHECK ((chunk_size > 0)),
    CONSTRAINT datasets_search_method_check CHECK (((search_method)::text = ANY (ARRAY[('vector'::character varying)::text, ('hybrid'::character varying)::text, ('keyword'::character varying)::text]))),
    CONSTRAINT datasets_visibility_check CHECK (((visibility)::text = ANY (ARRAY[('individual'::character varying)::text, ('team'::character varying)::text, ('organization'::character varying)::text])))
);


--
-- Name: COLUMN datasets.summary; Type: COMMENT; Schema: tenant_test_company; Owner: -
--

COMMENT ON COLUMN tenant_test_company.datasets.summary IS 'AI-generated summary synthesized from all document summaries in dataset';


--
-- Name: COLUMN datasets.summary_generated_at; Type: COMMENT; Schema: tenant_test_company; Owner: -
--

COMMENT ON COLUMN tenant_test_company.datasets.summary_generated_at IS 'Timestamp when dataset summary was generated';


--
-- Name: COLUMN datasets.summary_model; Type: COMMENT; Schema: tenant_test_company; Owner: -
--

COMMENT ON COLUMN tenant_test_company.datasets.summary_model IS 'AI model used to generate dataset summary';


--
-- Name: messages; Type: TABLE; Schema: tenant_test_company; Owner: -
--

CREATE TABLE tenant_test_company.messages (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    conversation_id uuid NOT NULL,
    user_id uuid NOT NULL,
    role character varying(20) NOT NULL,
    content text NOT NULL,
    content_type character varying(50) DEFAULT 'text'::character varying,
    token_count integer DEFAULT 0,
    model_used character varying(100),
    finish_reason character varying(50),
    metadata jsonb DEFAULT '{}'::jsonb,
    attachments jsonb DEFAULT '[]'::jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    embedding public.vector(1024),
    CONSTRAINT messages_content_type_check CHECK (((content_type)::text = ANY (ARRAY[('text'::character varying)::text, ('markdown'::character varying)::text, ('json'::character varying)::text, ('code'::character varying)::text]))),
    CONSTRAINT messages_role_check CHECK (((role)::text = ANY (ARRAY[('user'::character varying)::text, ('system'::character varying)::text, ('agent'::character varying)::text, ('tool'::character varying)::text])))
);


--
-- Name: conversation_context; Type: VIEW; Schema: tenant_test_company; Owner: -
--

CREATE VIEW tenant_test_company.conversation_context AS
 SELECT c.id AS conversation_id,
    c.title,
    c.user_id,
    c.agent_id,
    COALESCE(array_agg(DISTINCT jsonb_build_object('dataset_id', cd.dataset_id, 'dataset_name', d.name, 'search_method', d.search_method, 'specialized_language', d.specialized_language)) FILTER (WHERE (cd.dataset_id IS NOT NULL)), '{}'::jsonb[]) AS attached_datasets,
    ( SELECT array_agg(jsonb_build_object('role', m.role, 'content', m.content, 'created_at', m.created_at) ORDER BY m.created_at DESC) AS array_agg
           FROM tenant_test_company.messages m
          WHERE (m.conversation_id = c.id)
         LIMIT 10) AS recent_messages,
    cs.rag_enabled,
    cs.history_search_enabled,
    cs.history_search_scope,
    cs.search_method
   FROM (((tenant_test_company.conversations c
     LEFT JOIN tenant_test_company.conversation_datasets cd ON (((cd.conversation_id = c.id) AND (cd.is_active = true))))
     LEFT JOIN tenant_test_company.datasets d ON (((d.id = cd.dataset_id) AND (d.is_active = true))))
     LEFT JOIN tenant_test_company.conversation_settings cs ON ((cs.conversation_id = c.id)))
  GROUP BY c.id, c.title, c.user_id, c.agent_id, cs.rag_enabled, cs.history_search_enabled, cs.history_search_scope, cs.search_method;


--
-- Name: conversation_files; Type: TABLE; Schema: tenant_test_company; Owner: -
--

CREATE TABLE tenant_test_company.conversation_files (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    conversation_id uuid NOT NULL,
    filename text NOT NULL,
    original_filename text NOT NULL,
    content_type text NOT NULL,
    file_size_bytes bigint NOT NULL,
    file_path text NOT NULL,
    processed_chunks jsonb,
    processing_status text DEFAULT 'pending'::text,
    uploaded_by uuid NOT NULL,
    uploaded_at timestamp without time zone DEFAULT now(),
    processed_at timestamp without time zone,
    embeddings public.vector(1024),
    CONSTRAINT non_empty_filename CHECK ((length(TRIM(BOTH FROM filename)) > 0)),
    CONSTRAINT non_empty_original_filename CHECK ((length(TRIM(BOTH FROM original_filename)) > 0)),
    CONSTRAINT positive_file_size CHECK ((file_size_bytes > 0)),
    CONSTRAINT valid_processing_status CHECK ((processing_status = ANY (ARRAY['pending'::text, 'processing'::text, 'completed'::text, 'failed'::text])))
);


--
-- Name: document_chunks; Type: TABLE; Schema: tenant_test_company; Owner: -
--

CREATE TABLE tenant_test_company.document_chunks (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    document_id uuid NOT NULL,
    tenant_id uuid,
    user_id uuid NOT NULL,
    dataset_id uuid,
    chunk_index integer NOT NULL,
    content text NOT NULL,
    content_hash character varying(64) NOT NULL,
    token_count integer DEFAULT 0,
    embedding public.vector(1024),
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: documents; Type: TABLE; Schema: tenant_test_company; Owner: -
--

CREATE TABLE tenant_test_company.documents (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid,
    user_id uuid NOT NULL,
    dataset_id uuid,
    filename character varying(255) NOT NULL,
    original_filename character varying(255) NOT NULL,
    file_type character varying(100) NOT NULL,
    file_size_bytes bigint NOT NULL,
    file_hash character varying(64) NOT NULL,
    content_text text,
    chunk_count integer DEFAULT 0,
    processing_status character varying(50) DEFAULT 'pending'::character varying,
    error_message text,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    storage_type character varying(20) DEFAULT 'postgresql'::character varying,
    storage_ref text,
    summary text,
    summary_generated_at timestamp without time zone,
    summary_model character varying(100) DEFAULT 'llama-3.1-8b-instant'::character varying,
    chunks_processed integer DEFAULT 0,
    total_chunks_expected integer DEFAULT 0,
    processing_progress integer DEFAULT 0,
    processing_stage character varying(100) DEFAULT 'pending'::character varying,
    is_searchable boolean DEFAULT true,
    CONSTRAINT documents_processing_status_check CHECK (((processing_status)::text = ANY (ARRAY[('pending'::character varying)::text, ('processing'::character varying)::text, ('completed'::character varying)::text, ('failed'::character varying)::text])))
);


--
-- Name: COLUMN documents.summary; Type: COMMENT; Schema: tenant_test_company; Owner: -
--

COMMENT ON COLUMN tenant_test_company.documents.summary IS 'AI-generated 2-3 sentence summary of document content';


--
-- Name: COLUMN documents.summary_generated_at; Type: COMMENT; Schema: tenant_test_company; Owner: -
--

COMMENT ON COLUMN tenant_test_company.documents.summary_generated_at IS 'Timestamp when summary was generated';


--
-- Name: COLUMN documents.summary_model; Type: COMMENT; Schema: tenant_test_company; Owner: -
--

COMMENT ON COLUMN tenant_test_company.documents.summary_model IS 'AI model used to generate summary';


--
-- Name: COLUMN documents.is_searchable; Type: COMMENT; Schema: tenant_test_company; Owner: -
--

COMMENT ON COLUMN tenant_test_company.documents.is_searchable IS 'Tracks whether document content is indexed for full-text search. Large documents may be non-searchable until text extraction is implemented.';


--
-- Name: document_summaries; Type: TABLE; Schema: tenant_test_company; Owner: -
--

CREATE TABLE tenant_test_company.document_summaries (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    document_id uuid NOT NULL,
    user_id uuid NOT NULL,
    quick_summary text,
    detailed_analysis text,
    topics jsonb DEFAULT '[]'::jsonb,
    metadata jsonb DEFAULT '{}'::jsonb,
    confidence numeric(3,2) DEFAULT 0.0,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: COLUMN document_summaries.quick_summary; Type: COMMENT; Schema: tenant_test_company; Owner: -
--

COMMENT ON COLUMN tenant_test_company.document_summaries.quick_summary IS 'Brief 2-3 sentence summary of document';


--
-- Name: COLUMN document_summaries.detailed_analysis; Type: COMMENT; Schema: tenant_test_company; Owner: -
--

COMMENT ON COLUMN tenant_test_company.document_summaries.detailed_analysis IS 'Comprehensive analysis of document content, themes, and key points';


--
-- Name: COLUMN document_summaries.topics; Type: COMMENT; Schema: tenant_test_company; Owner: -
--

COMMENT ON COLUMN tenant_test_company.document_summaries.topics IS 'JSONB array of identified topics/themes in document';


--
-- Name: COLUMN document_summaries.confidence; Type: COMMENT; Schema: tenant_test_company; Owner: -
--

COMMENT ON COLUMN tenant_test_company.document_summaries.confidence IS 'AI confidence score for summary quality (0.0-1.0)';


--
-- Name: documents_compat; Type: VIEW; Schema: tenant_test_company; Owner: -
--

CREATE VIEW tenant_test_company.documents_compat AS
 SELECT documents.id,
    documents.filename,
    documents.original_filename AS original_name,
    documents.dataset_id,
    documents.file_size_bytes AS file_size,
    documents.tenant_id AS team_id,
    documents.user_id,
    documents.file_type,
    documents.file_hash,
    documents.content_text,
    documents.chunk_count,
    documents.processing_status,
    documents.error_message,
    documents.metadata,
    documents.created_at,
    documents.updated_at,
    documents.storage_type,
    documents.storage_ref,
    documents.summary,
    documents.summary_generated_at,
    documents.summary_model,
    documents.chunks_processed,
    documents.total_chunks_expected,
    documents.processing_progress,
    documents.processing_stage,
    documents.is_searchable
   FROM tenant_test_company.documents;


--
-- Name: subagent_executions; Type: TABLE; Schema: tenant_test_company; Owner: -
--

CREATE TABLE tenant_test_company.subagent_executions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    parent_agent_id uuid,
    conversation_id uuid,
    execution_id character varying(255) NOT NULL,
    subagent_type character varying(50) NOT NULL,
    subagent_id character varying(255) NOT NULL,
    task_description text,
    status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    input_data jsonb,
    output_data jsonb,
    tool_calls jsonb,
    error_message text,
    execution_time_ms integer,
    started_at timestamp without time zone DEFAULT now(),
    completed_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    CONSTRAINT subagent_status_check CHECK (((status)::text = ANY (ARRAY[('pending'::character varying)::text, ('running'::character varying)::text, ('completed'::character varying)::text, ('failed'::character varying)::text, ('cancelled'::character varying)::text])))
);


--
-- Name: TABLE subagent_executions; Type: COMMENT; Schema: tenant_test_company; Owner: -
--

COMMENT ON TABLE tenant_test_company.subagent_executions IS 'Tracks execution of subagents spawned during complex task handling';


--
-- Name: task_classifications; Type: TABLE; Schema: tenant_test_company; Owner: -
--

CREATE TABLE tenant_test_company.task_classifications (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    conversation_id uuid,
    query_hash character varying(64) NOT NULL,
    query_text text NOT NULL,
    complexity character varying(50) NOT NULL,
    confidence double precision NOT NULL,
    primary_intent character varying(50),
    subagent_plan jsonb,
    estimated_tools text[],
    parallel_execution boolean DEFAULT false,
    requires_confirmation boolean DEFAULT false,
    reasoning text,
    created_at timestamp without time zone DEFAULT now(),
    expires_at timestamp without time zone DEFAULT (now() + '01:00:00'::interval),
    CONSTRAINT complexity_check CHECK (((complexity)::text = ANY (ARRAY[('simple'::character varying)::text, ('tool_assisted'::character varying)::text, ('multi_step'::character varying)::text, ('research'::character varying)::text, ('implementation'::character varying)::text, ('complex'::character varying)::text])))
);


--
-- Name: TABLE task_classifications; Type: COMMENT; Schema: tenant_test_company; Owner: -
--

COMMENT ON TABLE tenant_test_company.task_classifications IS 'Cache of task classification results for performance';


--
-- Name: team_memberships; Type: TABLE; Schema: tenant_test_company; Owner: -
--

CREATE TABLE tenant_test_company.team_memberships (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    team_id uuid NOT NULL,
    user_id uuid NOT NULL,
    team_permission character varying(20) DEFAULT 'read'::character varying NOT NULL,
    resource_permissions jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    status character varying(20) DEFAULT 'accepted'::character varying,
    invited_at timestamp with time zone DEFAULT now(),
    responded_at timestamp with time zone,
    is_observable boolean DEFAULT false,
    observable_consent_status character varying(20) DEFAULT 'none'::character varying,
    observable_consent_at timestamp with time zone,
    CONSTRAINT check_observable_consent_status CHECK (((observable_consent_status)::text = ANY ((ARRAY['none'::character varying, 'pending'::character varying, 'approved'::character varying, 'revoked'::character varying])::text[]))),
    CONSTRAINT check_team_permission CHECK (((team_permission)::text = ANY ((ARRAY['read'::character varying, 'share'::character varying, 'manager'::character varying])::text[]))),
    CONSTRAINT team_memberships_status_check CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'accepted'::character varying, 'declined'::character varying])::text[])))
);


--
-- Name: COLUMN team_memberships.team_permission; Type: COMMENT; Schema: tenant_test_company; Owner: -
--

COMMENT ON COLUMN tenant_test_company.team_memberships.team_permission IS 'Team role: read=Member (view only), share=Contributor (can share resources), manager=Manager (can manage members + view Observable activity)';


--
-- Name: COLUMN team_memberships.is_observable; Type: COMMENT; Schema: tenant_test_company; Owner: -
--

COMMENT ON COLUMN tenant_test_company.team_memberships.is_observable IS 'Member consents to team managers viewing their activity';


--
-- Name: COLUMN team_memberships.observable_consent_status; Type: COMMENT; Schema: tenant_test_company; Owner: -
--

COMMENT ON COLUMN tenant_test_company.team_memberships.observable_consent_status IS 'Consent workflow status: none, pending, approved, revoked';


--
-- Name: COLUMN team_memberships.observable_consent_at; Type: COMMENT; Schema: tenant_test_company; Owner: -
--

COMMENT ON COLUMN tenant_test_company.team_memberships.observable_consent_at IS 'Timestamp when Observable status was approved';


--
-- Name: team_resource_shares; Type: TABLE; Schema: tenant_test_company; Owner: -
--

CREATE TABLE tenant_test_company.team_resource_shares (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    team_id uuid NOT NULL,
    resource_type character varying(20) NOT NULL,
    resource_id uuid NOT NULL,
    shared_by uuid NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    CONSTRAINT team_resource_shares_resource_type_check CHECK (((resource_type)::text = ANY ((ARRAY['agent'::character varying, 'dataset'::character varying])::text[])))
);


--
-- Name: TABLE team_resource_shares; Type: COMMENT; Schema: tenant_test_company; Owner: -
--

COMMENT ON TABLE tenant_test_company.team_resource_shares IS 'Junction table for sharing agents/datasets with collaboration teams';


--
-- Name: COLUMN team_resource_shares.resource_type; Type: COMMENT; Schema: tenant_test_company; Owner: -
--

COMMENT ON COLUMN tenant_test_company.team_resource_shares.resource_type IS 'Type of resource: agent or dataset';


--
-- Name: COLUMN team_resource_shares.resource_id; Type: COMMENT; Schema: tenant_test_company; Owner: -
--

COMMENT ON COLUMN tenant_test_company.team_resource_shares.resource_id IS 'UUID of the agent or dataset being shared';


--
-- Name: COLUMN team_resource_shares.shared_by; Type: COMMENT; Schema: tenant_test_company; Owner: -
--

COMMENT ON COLUMN tenant_test_company.team_resource_shares.shared_by IS 'User who shared this resource with the team';


--
-- Name: teams; Type: TABLE; Schema: tenant_test_company; Owner: -
--

CREATE TABLE tenant_test_company.teams (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    tenant_id uuid NOT NULL,
    owner_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: tenants; Type: TABLE; Schema: tenant_test_company; Owner: -
--

CREATE TABLE tenant_test_company.tenants (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(255) NOT NULL,
    domain character varying(255) NOT NULL,
    plan_type character varying(50) DEFAULT 'free'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: teams_compat; Type: VIEW; Schema: tenant_test_company; Owner: -
--

CREATE VIEW tenant_test_company.teams_compat AS
 SELECT tenants.id,
    tenants.name,
    tenants.domain,
    tenants.plan_type AS tier,
    tenants.created_at,
    tenants.updated_at
   FROM tenant_test_company.tenants;


--
-- Name: user_accessible_resources; Type: VIEW; Schema: tenant_test_company; Owner: -
--

CREATE VIEW tenant_test_company.user_accessible_resources AS
 SELECT tm.user_id,
    trs.resource_type,
    trs.resource_id,
    max(
        CASE
            WHEN ((tm.resource_permissions -> (((trs.resource_type)::text || ':'::text) || (trs.resource_id)::text)) = '"edit"'::jsonb) THEN 'edit'::text
            WHEN ((tm.resource_permissions -> (((trs.resource_type)::text || ':'::text) || (trs.resource_id)::text)) = '"read"'::jsonb) THEN 'read'::text
            ELSE 'none'::text
        END) AS best_permission,
    count(DISTINCT tm.team_id) AS shared_in_teams,
    array_agg(DISTINCT tm.team_id) AS team_ids,
    min(trs.created_at) AS first_shared_at
   FROM (tenant_test_company.team_memberships tm
     JOIN tenant_test_company.team_resource_shares trs ON ((tm.team_id = trs.team_id)))
  WHERE (tm.resource_permissions ? (((trs.resource_type)::text || ':'::text) || (trs.resource_id)::text))
  GROUP BY tm.user_id, trs.resource_type, trs.resource_id;


--
-- Name: VIEW user_accessible_resources; Type: COMMENT; Schema: tenant_test_company; Owner: -
--

COMMENT ON VIEW tenant_test_company.user_accessible_resources IS 'Aggregated view showing all resources accessible to each user with best permission level';


--
-- Name: user_resource_access; Type: VIEW; Schema: tenant_test_company; Owner: -
--

CREATE VIEW tenant_test_company.user_resource_access AS
 SELECT tm.user_id,
    trs.resource_type,
    trs.resource_id,
    (tm.resource_permissions -> (((trs.resource_type)::text || ':'::text) || (trs.resource_id)::text)) AS permission,
    tm.team_id,
    tm.team_permission,
    trs.shared_by,
    trs.created_at
   FROM (tenant_test_company.team_memberships tm
     JOIN tenant_test_company.team_resource_shares trs ON ((tm.team_id = trs.team_id)))
  WHERE (tm.resource_permissions ? (((trs.resource_type)::text || ':'::text) || (trs.resource_id)::text));


--
-- Name: VIEW user_resource_access; Type: COMMENT; Schema: tenant_test_company; Owner: -
--

COMMENT ON VIEW tenant_test_company.user_resource_access IS 'Flattened view of user access to resources via team memberships';


--
-- Name: users; Type: TABLE; Schema: tenant_test_company; Owner: -
--

CREATE TABLE tenant_test_company.users (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    email character varying(255) NOT NULL,
    username character varying(100) NOT NULL,
    full_name character varying(255),
    tenant_id uuid NOT NULL,
    role character varying(50) DEFAULT 'student'::character varying,
    is_active boolean DEFAULT true,
    preferences jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    last_login timestamp with time zone,
    CONSTRAINT users_role_check CHECK (((role)::text = ANY (ARRAY[('admin'::character varying)::text, ('developer'::character varying)::text, ('analyst'::character varying)::text, ('student'::character varying)::text])))
);


--
-- Name: auth_logs; Type: TABLE; Schema: tenant_test_company; Owner: -
--

CREATE TABLE tenant_test_company.auth_logs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id text NOT NULL,
    email text NOT NULL,
    event_type text NOT NULL,
    success boolean DEFAULT true NOT NULL,
    failure_reason text,
    ip_address text,
    user_agent text,
    tenant_domain text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb,
    CONSTRAINT auth_logs_event_type_check CHECK ((event_type = ANY (ARRAY['login'::text, 'logout'::text, 'failed_login'::text])))
);


--
-- Name: TABLE auth_logs; Type: COMMENT; Schema: tenant_test_company; Owner: -
--

COMMENT ON TABLE tenant_test_company.auth_logs IS 'Authentication event logs for security auditing and observability';


--
-- Name: users_compat; Type: VIEW; Schema: tenant_test_company; Owner: -
--

CREATE VIEW tenant_test_company.users_compat AS
 SELECT users.id,
    users.email,
    users.full_name AS name,
    users.username,
    users.tenant_id AS team_id,
    users.role,
    users.is_active,
    users.preferences,
    users.created_at,
    users.updated_at,
    users.last_login
   FROM tenant_test_company.users;


--
-- Name: workflow_executions; Type: TABLE; Schema: tenant_test_company; Owner: -
--

CREATE TABLE tenant_test_company.workflow_executions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    workflow_id character varying(255) NOT NULL,
    workflow_type character varying(50) NOT NULL,
    parent_agent_id uuid,
    conversation_id uuid,
    created_by character varying(255) NOT NULL,
    workflow_config jsonb,
    status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    results jsonb,
    error_message text,
    started_at timestamp without time zone,
    completed_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    CONSTRAINT workflow_status_check CHECK (((status)::text = ANY (ARRAY[('pending'::character varying)::text, ('running'::character varying)::text, ('completed'::character varying)::text, ('failed'::character varying)::text, ('cancelled'::character varying)::text]))),
    CONSTRAINT workflow_type_check CHECK (((workflow_type)::text = ANY (ARRAY[('sequential'::character varying)::text, ('parallel'::character varying)::text, ('conditional'::character varying)::text, ('pipeline'::character varying)::text, ('map_reduce'::character varying)::text])))
);


--
-- Name: TABLE workflow_executions; Type: COMMENT; Schema: tenant_test_company; Owner: -
--

COMMENT ON TABLE tenant_test_company.workflow_executions IS 'Tracks multi-agent workflow execution instances';


--
-- Name: agent_datasets agent_datasets_agent_id_dataset_id_key; Type: CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.agent_datasets
    ADD CONSTRAINT agent_datasets_agent_id_dataset_id_key UNIQUE (agent_id, dataset_id);


--
-- Name: agent_datasets agent_datasets_pkey; Type: CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.agent_datasets
    ADD CONSTRAINT agent_datasets_pkey PRIMARY KEY (id);


--
-- Name: agent_messages agent_messages_pkey; Type: CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.agent_messages
    ADD CONSTRAINT agent_messages_pkey PRIMARY KEY (id);


--
-- Name: auth_logs auth_logs_pkey; Type: CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.auth_logs
    ADD CONSTRAINT auth_logs_pkey PRIMARY KEY (id);


--
-- Name: agents agents_pkey; Type: CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.agents
    ADD CONSTRAINT agents_pkey PRIMARY KEY (id);


--
-- Name: conversation_datasets conversation_datasets_pkey; Type: CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.conversation_datasets
    ADD CONSTRAINT conversation_datasets_pkey PRIMARY KEY (conversation_id, dataset_id);


--
-- Name: conversation_files conversation_files_pkey; Type: CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.conversation_files
    ADD CONSTRAINT conversation_files_pkey PRIMARY KEY (id);


--
-- Name: conversation_settings conversation_settings_pkey; Type: CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.conversation_settings
    ADD CONSTRAINT conversation_settings_pkey PRIMARY KEY (id);


--
-- Name: conversations conversations_pkey; Type: CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.conversations
    ADD CONSTRAINT conversations_pkey PRIMARY KEY (id);


--
-- Name: datasets datasets_pkey; Type: CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.datasets
    ADD CONSTRAINT datasets_pkey PRIMARY KEY (id);


--
-- Name: document_chunks document_chunks_document_id_chunk_index_key; Type: CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.document_chunks
    ADD CONSTRAINT document_chunks_document_id_chunk_index_key UNIQUE (document_id, chunk_index);


--
-- Name: document_chunks document_chunks_pkey; Type: CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.document_chunks
    ADD CONSTRAINT document_chunks_pkey PRIMARY KEY (id);


--
-- Name: documents documents_pkey; Type: CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.documents
    ADD CONSTRAINT documents_pkey PRIMARY KEY (id);


--
-- Name: document_summaries document_summaries_pkey; Type: CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.document_summaries
    ADD CONSTRAINT document_summaries_pkey PRIMARY KEY (id);


--
-- Name: document_summaries document_summaries_document_id_key; Type: CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.document_summaries
    ADD CONSTRAINT document_summaries_document_id_key UNIQUE (document_id);


--
-- Name: messages messages_pkey; Type: CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.messages
    ADD CONSTRAINT messages_pkey PRIMARY KEY (id);


--
-- Name: subagent_executions subagent_executions_pkey; Type: CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.subagent_executions
    ADD CONSTRAINT subagent_executions_pkey PRIMARY KEY (id);


--
-- Name: task_classifications task_classifications_pkey; Type: CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.task_classifications
    ADD CONSTRAINT task_classifications_pkey PRIMARY KEY (id);


--
-- Name: team_memberships team_memberships_pkey; Type: CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.team_memberships
    ADD CONSTRAINT team_memberships_pkey PRIMARY KEY (id);


--
-- Name: team_memberships team_memberships_team_id_user_id_key; Type: CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.team_memberships
    ADD CONSTRAINT team_memberships_team_id_user_id_key UNIQUE (team_id, user_id);


--
-- Name: team_resource_shares team_resource_shares_pkey; Type: CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.team_resource_shares
    ADD CONSTRAINT team_resource_shares_pkey PRIMARY KEY (id);


--
-- Name: team_resource_shares team_resource_shares_team_id_resource_type_resource_id_key; Type: CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.team_resource_shares
    ADD CONSTRAINT team_resource_shares_team_id_resource_type_resource_id_key UNIQUE (team_id, resource_type, resource_id);


--
-- Name: tenants teams_domain_key; Type: CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.tenants
    ADD CONSTRAINT teams_domain_key UNIQUE (domain);


--
-- Name: tenants teams_pkey; Type: CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.tenants
    ADD CONSTRAINT teams_pkey PRIMARY KEY (id);


--
-- Name: teams teams_pkey1; Type: CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.teams
    ADD CONSTRAINT teams_pkey1 PRIMARY KEY (id);


--
-- Name: users users_email_team_id_key; Type: CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.users
    ADD CONSTRAINT users_email_team_id_key UNIQUE (email, tenant_id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: users users_username_key; Type: CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.users
    ADD CONSTRAINT users_username_key UNIQUE (username);


--
-- Name: workflow_executions workflow_executions_pkey; Type: CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.workflow_executions
    ADD CONSTRAINT workflow_executions_pkey PRIMARY KEY (id);


--
-- Name: workflow_executions workflow_executions_workflow_id_key; Type: CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.workflow_executions
    ADD CONSTRAINT workflow_executions_workflow_id_key UNIQUE (workflow_id);


--
-- Name: idx_agent_datasets_agent_id; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_agent_datasets_agent_id ON tenant_test_company.agent_datasets USING btree (agent_id);


--
-- Name: idx_agent_datasets_dataset_id; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_agent_datasets_dataset_id ON tenant_test_company.agent_datasets USING btree (dataset_id);


--
-- Name: idx_agents_created_by; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_agents_created_by ON tenant_test_company.agents USING btree (created_by);


--
-- Name: idx_agents_tenant_id; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_agents_tenant_id ON tenant_test_company.agents USING btree (tenant_id);


--
-- Name: idx_agents_visibility; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_agents_visibility ON tenant_test_company.agents USING btree (visibility);


--
-- Name: idx_auth_logs_created_at; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_auth_logs_created_at ON tenant_test_company.auth_logs USING btree (created_at DESC);


--
-- Name: idx_auth_logs_email; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_auth_logs_email ON tenant_test_company.auth_logs USING btree (email);


--
-- Name: idx_auth_logs_event_created; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_auth_logs_event_created ON tenant_test_company.auth_logs USING btree (event_type, created_at DESC);


--
-- Name: idx_auth_logs_event_type; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_auth_logs_event_type ON tenant_test_company.auth_logs USING btree (event_type);


--
-- Name: idx_auth_logs_tenant_domain; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_auth_logs_tenant_domain ON tenant_test_company.auth_logs USING btree (tenant_domain);


--
-- Name: idx_auth_logs_user_id; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_auth_logs_user_id ON tenant_test_company.auth_logs USING btree (user_id);


--
-- Name: idx_conversation_datasets_conversation_id; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_conversation_datasets_conversation_id ON tenant_test_company.conversation_datasets USING btree (conversation_id);


--
-- Name: idx_conversation_datasets_dataset_id; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_conversation_datasets_dataset_id ON tenant_test_company.conversation_datasets USING btree (dataset_id);


--
-- Name: idx_conversation_files_embeddings; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_conversation_files_embeddings ON tenant_test_company.conversation_files USING ivfflat (embeddings public.vector_cosine_ops) WITH (lists='100');


--
-- Name: idx_conversation_settings_conversation_id; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_conversation_settings_conversation_id ON tenant_test_company.conversation_settings USING btree (conversation_id);


--
-- Name: idx_conversations_tenant_id; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_conversations_tenant_id ON tenant_test_company.conversations USING btree (tenant_id);


--
-- Name: idx_conversations_user_id; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_conversations_user_id ON tenant_test_company.conversations USING btree (user_id);


--
-- Name: idx_datasets_conversation_id; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_datasets_conversation_id ON tenant_test_company.datasets USING btree (conversation_id);


--
-- Name: idx_datasets_created_by; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_datasets_created_by ON tenant_test_company.datasets USING btree (created_by);


--
-- Name: idx_datasets_search_method; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_datasets_search_method ON tenant_test_company.datasets USING btree (search_method);


--
-- Name: idx_datasets_summary_generated_at; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_datasets_summary_generated_at ON tenant_test_company.datasets USING btree (summary_generated_at) WHERE (summary IS NOT NULL);


--
-- Name: idx_datasets_tenant_id; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_datasets_tenant_id ON tenant_test_company.datasets USING btree (tenant_id);


--
-- Name: idx_document_chunks_content_fts; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_document_chunks_content_fts ON tenant_test_company.document_chunks USING gin (to_tsvector('english'::regconfig, content));


--
-- Name: idx_document_chunks_embedding_hnsw; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_document_chunks_embedding_hnsw ON tenant_test_company.document_chunks USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: idx_document_chunks_tenant_id; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_document_chunks_tenant_id ON tenant_test_company.document_chunks USING btree (tenant_id);


--
-- Name: idx_document_chunks_user_id; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_document_chunks_user_id ON tenant_test_company.document_chunks USING btree (user_id);


--
-- Name: idx_documents_content_fts; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_documents_content_fts ON tenant_test_company.documents USING gin (to_tsvector('english'::regconfig, content_text)) WHERE ((content_text IS NOT NULL) AND (length(content_text) < 1048575) AND (is_searchable = true));


--
-- Name: INDEX idx_documents_content_fts; Type: COMMENT; Schema: tenant_test_company; Owner: -
--

COMMENT ON INDEX tenant_test_company.idx_documents_content_fts IS 'Conditional GIN index for full-text search that excludes oversized content to prevent tsvector size limit errors';


--
-- Name: idx_documents_summary_generated_at; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_documents_summary_generated_at ON tenant_test_company.documents USING btree (summary_generated_at) WHERE (summary IS NOT NULL);


--
-- Name: idx_documents_tenant_id; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_documents_tenant_id ON tenant_test_company.documents USING btree (tenant_id);


--
-- Name: idx_documents_user_id; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_documents_user_id ON tenant_test_company.documents USING btree (user_id);


--
-- Name: idx_messages_content_fts; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_messages_content_fts ON tenant_test_company.messages USING gin (to_tsvector('english'::regconfig, content));


--
-- Name: idx_messages_conversation_id; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_messages_conversation_id ON tenant_test_company.messages USING btree (conversation_id);


--
-- Name: idx_messages_created_at; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_messages_created_at ON tenant_test_company.messages USING btree (created_at);


--
-- Name: idx_messages_embedding_hnsw; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_messages_embedding_hnsw ON tenant_test_company.messages USING hnsw (embedding public.vector_cosine_ops) WHERE (embedding IS NOT NULL);


--
-- Name: idx_messages_role; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_messages_role ON tenant_test_company.messages USING btree (role);


--
-- Name: idx_messages_user_id; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_messages_user_id ON tenant_test_company.messages USING btree (user_id);


--
-- Name: idx_team_memberships_observable; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_team_memberships_observable ON tenant_test_company.team_memberships USING btree (team_id, is_observable, observable_consent_status) WHERE ((is_observable = true) AND ((observable_consent_status)::text = 'approved'::text));


--
-- Name: INDEX idx_team_memberships_observable; Type: COMMENT; Schema: tenant_test_company; Owner: -
--

COMMENT ON INDEX tenant_test_company.idx_team_memberships_observable IS 'Optimizes queries for Observable member activity (partial index for approved Observable members only)';


--
-- Name: idx_team_memberships_permission; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_team_memberships_permission ON tenant_test_company.team_memberships USING btree (team_id, team_permission);


--
-- Name: INDEX idx_team_memberships_permission; Type: COMMENT; Schema: tenant_test_company; Owner: -
--

COMMENT ON INDEX tenant_test_company.idx_team_memberships_permission IS 'Optimizes role-based permission checks (finding managers, contributors, etc.)';


--
-- Name: idx_team_memberships_resources; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_team_memberships_resources ON tenant_test_company.team_memberships USING gin (resource_permissions);


--
-- Name: idx_team_memberships_status; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_team_memberships_status ON tenant_test_company.team_memberships USING btree (user_id, status);


--
-- Name: idx_team_memberships_team_id; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_team_memberships_team_id ON tenant_test_company.team_memberships USING btree (team_id);


--
-- Name: idx_team_memberships_team_status; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_team_memberships_team_status ON tenant_test_company.team_memberships USING btree (team_id, status);


--
-- Name: idx_team_memberships_user_id; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_team_memberships_user_id ON tenant_test_company.team_memberships USING btree (user_id);


--
-- Name: idx_teams_domain; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_teams_domain ON tenant_test_company.tenants USING btree (domain);


--
-- Name: idx_teams_owner_id; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_teams_owner_id ON tenant_test_company.teams USING btree (owner_id);


--
-- Name: idx_teams_tenant_id; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_teams_tenant_id ON tenant_test_company.teams USING btree (tenant_id);


--
-- Name: idx_tenant_test_company_agent_msg_conversation; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_tenant_test_company_agent_msg_conversation ON tenant_test_company.agent_messages USING btree (conversation_id);


--
-- Name: idx_tenant_test_company_agent_msg_execution; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_tenant_test_company_agent_msg_execution ON tenant_test_company.agent_messages USING btree (execution_id);


--
-- Name: idx_tenant_test_company_agent_msg_to_agent; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_tenant_test_company_agent_msg_to_agent ON tenant_test_company.agent_messages USING btree (to_agent_id) WHERE (processed = false);


--
-- Name: idx_tenant_test_company_subagent_exec_conversation; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_tenant_test_company_subagent_exec_conversation ON tenant_test_company.subagent_executions USING btree (conversation_id);


--
-- Name: idx_tenant_test_company_subagent_exec_execution_id; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_tenant_test_company_subagent_exec_execution_id ON tenant_test_company.subagent_executions USING btree (execution_id);


--
-- Name: idx_tenant_test_company_subagent_exec_parent; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_tenant_test_company_subagent_exec_parent ON tenant_test_company.subagent_executions USING btree (parent_agent_id);


--
-- Name: idx_tenant_test_company_subagent_exec_status; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_tenant_test_company_subagent_exec_status ON tenant_test_company.subagent_executions USING btree (status);


--
-- Name: idx_tenant_test_company_task_class_conversation; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_tenant_test_company_task_class_conversation ON tenant_test_company.task_classifications USING btree (conversation_id);


--
-- Name: idx_tenant_test_company_task_class_expires; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_tenant_test_company_task_class_expires ON tenant_test_company.task_classifications USING btree (expires_at);


--
-- Name: idx_tenant_test_company_task_class_query_hash; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_tenant_test_company_task_class_query_hash ON tenant_test_company.task_classifications USING btree (query_hash);


--
-- Name: idx_tenant_test_company_workflow_exec_conversation; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_tenant_test_company_workflow_exec_conversation ON tenant_test_company.workflow_executions USING btree (conversation_id);


--
-- Name: idx_tenant_test_company_workflow_exec_status; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_tenant_test_company_workflow_exec_status ON tenant_test_company.workflow_executions USING btree (status) WHERE ((status)::text = ANY (ARRAY[('pending'::character varying)::text, ('running'::character varying)::text]));


--
-- Name: idx_trs_lookup; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_trs_lookup ON tenant_test_company.team_resource_shares USING btree (team_id, resource_type, resource_id);


--
-- Name: idx_trs_resource; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_trs_resource ON tenant_test_company.team_resource_shares USING btree (resource_type, resource_id);


--
-- Name: idx_trs_shared_by; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_trs_shared_by ON tenant_test_company.team_resource_shares USING btree (shared_by);


--
-- Name: idx_trs_team; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_trs_team ON tenant_test_company.team_resource_shares USING btree (team_id);


--
-- Name: idx_users_email; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_users_email ON tenant_test_company.users USING btree (email);


--
-- Name: idx_users_tenant_id; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_users_tenant_id ON tenant_test_company.users USING btree (tenant_id);


--
-- Name: idx_messages_conversation_created; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_messages_conversation_created ON tenant_test_company.messages USING btree (conversation_id, created_at ASC);


--
-- Name: idx_conversations_user_updated; Type: INDEX; Schema: tenant_test_company; Owner: -
--

CREATE INDEX idx_conversations_user_updated ON tenant_test_company.conversations USING btree (user_id, is_archived, updated_at DESC);


--
-- Name: agents trigger_agents_updated_at; Type: TRIGGER; Schema: tenant_test_company; Owner: -
--

CREATE TRIGGER trigger_agents_updated_at BEFORE UPDATE ON tenant_test_company.agents FOR EACH ROW EXECUTE FUNCTION tenant_test_company.update_updated_at_column();


--
-- Name: team_memberships trigger_auto_unshare; Type: TRIGGER; Schema: tenant_test_company; Owner: -
--

CREATE TRIGGER trigger_auto_unshare BEFORE UPDATE OF team_permission ON tenant_test_company.team_memberships FOR EACH ROW EXECUTE FUNCTION tenant_test_company.auto_unshare_on_permission_downgrade();


--
-- Name: team_resource_shares trigger_cleanup_resource_permissions; Type: TRIGGER; Schema: tenant_test_company; Owner: -
--

CREATE TRIGGER trigger_cleanup_resource_permissions BEFORE DELETE ON tenant_test_company.team_resource_shares FOR EACH ROW EXECUTE FUNCTION tenant_test_company.cleanup_resource_permissions();


--
-- Name: conversation_settings trigger_conversation_settings_updated_at; Type: TRIGGER; Schema: tenant_test_company; Owner: -
--

CREATE TRIGGER trigger_conversation_settings_updated_at BEFORE UPDATE ON tenant_test_company.conversation_settings FOR EACH ROW EXECUTE FUNCTION tenant_test_company.update_updated_at_column();


--
-- Name: conversations trigger_conversations_updated_at; Type: TRIGGER; Schema: tenant_test_company; Owner: -
--

CREATE TRIGGER trigger_conversations_updated_at BEFORE UPDATE ON tenant_test_company.conversations FOR EACH ROW EXECUTE FUNCTION tenant_test_company.update_updated_at_column();


--
-- Name: datasets trigger_datasets_updated_at; Type: TRIGGER; Schema: tenant_test_company; Owner: -
--

CREATE TRIGGER trigger_datasets_updated_at BEFORE UPDATE ON tenant_test_company.datasets FOR EACH ROW EXECUTE FUNCTION tenant_test_company.update_updated_at_column();


--
-- Name: documents trigger_documents_updated_at; Type: TRIGGER; Schema: tenant_test_company; Owner: -
--

CREATE TRIGGER trigger_documents_updated_at BEFORE UPDATE ON tenant_test_company.documents FOR EACH ROW EXECUTE FUNCTION tenant_test_company.update_updated_at_column();


--
-- Name: tenants trigger_teams_updated_at; Type: TRIGGER; Schema: tenant_test_company; Owner: -
--

CREATE TRIGGER trigger_teams_updated_at BEFORE UPDATE ON tenant_test_company.tenants FOR EACH ROW EXECUTE FUNCTION tenant_test_company.update_updated_at_column();


--
-- Name: users trigger_users_updated_at; Type: TRIGGER; Schema: tenant_test_company; Owner: -
--

CREATE TRIGGER trigger_users_updated_at BEFORE UPDATE ON tenant_test_company.users FOR EACH ROW EXECUTE FUNCTION tenant_test_company.update_updated_at_column();


--
-- Name: team_resource_shares trigger_validate_resource_share; Type: TRIGGER; Schema: tenant_test_company; Owner: -
--

CREATE TRIGGER trigger_validate_resource_share BEFORE INSERT ON tenant_test_company.team_resource_shares FOR EACH ROW EXECUTE FUNCTION tenant_test_company.validate_resource_share();


--
-- Name: subagent_executions update_subagent_executions_updated_at; Type: TRIGGER; Schema: tenant_test_company; Owner: -
--

CREATE TRIGGER update_subagent_executions_updated_at BEFORE UPDATE ON tenant_test_company.subagent_executions FOR EACH ROW EXECUTE FUNCTION tenant_test_company.update_subagent_updated_at();


--
-- Name: workflow_executions update_workflow_executions_updated_at; Type: TRIGGER; Schema: tenant_test_company; Owner: -
--

CREATE TRIGGER update_workflow_executions_updated_at BEFORE UPDATE ON tenant_test_company.workflow_executions FOR EACH ROW EXECUTE FUNCTION tenant_test_company.update_subagent_updated_at();


--
-- Name: agent_datasets agent_datasets_agent_id_fkey; Type: FK CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.agent_datasets
    ADD CONSTRAINT agent_datasets_agent_id_fkey FOREIGN KEY (agent_id) REFERENCES tenant_test_company.agents(id) ON DELETE CASCADE;


--
-- Name: agent_datasets agent_datasets_dataset_id_fkey; Type: FK CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.agent_datasets
    ADD CONSTRAINT agent_datasets_dataset_id_fkey FOREIGN KEY (dataset_id) REFERENCES tenant_test_company.datasets(id) ON DELETE CASCADE;


--
-- Name: agent_messages agent_messages_conversation_id_fkey; Type: FK CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.agent_messages
    ADD CONSTRAINT agent_messages_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES tenant_test_company.conversations(id) ON DELETE CASCADE;


--
-- Name: agents agents_created_by_fkey; Type: FK CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.agents
    ADD CONSTRAINT agents_created_by_fkey FOREIGN KEY (created_by) REFERENCES tenant_test_company.users(id) ON DELETE CASCADE;


--
-- Name: agents agents_tenant_id_fkey; Type: FK CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.agents
    ADD CONSTRAINT agents_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenant_test_company.tenants(id) ON DELETE CASCADE;


--
-- Name: conversation_datasets conversation_datasets_attached_by_fkey; Type: FK CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.conversation_datasets
    ADD CONSTRAINT conversation_datasets_attached_by_fkey FOREIGN KEY (attached_by) REFERENCES tenant_test_company.users(id) ON DELETE CASCADE;


--
-- Name: conversation_datasets conversation_datasets_conversation_id_fkey; Type: FK CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.conversation_datasets
    ADD CONSTRAINT conversation_datasets_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES tenant_test_company.conversations(id) ON DELETE CASCADE;


--
-- Name: conversation_datasets conversation_datasets_dataset_id_fkey; Type: FK CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.conversation_datasets
    ADD CONSTRAINT conversation_datasets_dataset_id_fkey FOREIGN KEY (dataset_id) REFERENCES tenant_test_company.datasets(id) ON DELETE CASCADE;


--
-- Name: conversation_files conversation_files_conversation_id_fkey; Type: FK CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.conversation_files
    ADD CONSTRAINT conversation_files_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES tenant_test_company.conversations(id) ON DELETE CASCADE;


--
-- Name: conversation_files conversation_files_uploaded_by_fkey; Type: FK CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.conversation_files
    ADD CONSTRAINT conversation_files_uploaded_by_fkey FOREIGN KEY (uploaded_by) REFERENCES tenant_test_company.users(id);


--
-- Name: conversation_settings conversation_settings_conversation_id_fkey; Type: FK CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.conversation_settings
    ADD CONSTRAINT conversation_settings_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES tenant_test_company.conversations(id) ON DELETE CASCADE;


--
-- Name: conversations conversations_agent_id_fkey; Type: FK CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.conversations
    ADD CONSTRAINT conversations_agent_id_fkey FOREIGN KEY (agent_id) REFERENCES tenant_test_company.agents(id) ON DELETE SET NULL;


--
-- Name: conversations conversations_tenant_id_fkey; Type: FK CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.conversations
    ADD CONSTRAINT conversations_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenant_test_company.tenants(id) ON DELETE CASCADE;


--
-- Name: conversations conversations_user_id_fkey; Type: FK CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.conversations
    ADD CONSTRAINT conversations_user_id_fkey FOREIGN KEY (user_id) REFERENCES tenant_test_company.users(id) ON DELETE CASCADE;


--
-- Name: datasets datasets_conversation_id_fkey; Type: FK CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.datasets
    ADD CONSTRAINT datasets_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES tenant_test_company.conversations(id) ON DELETE SET NULL;


--
-- Name: datasets datasets_created_by_fkey; Type: FK CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.datasets
    ADD CONSTRAINT datasets_created_by_fkey FOREIGN KEY (created_by) REFERENCES tenant_test_company.users(id) ON DELETE CASCADE;


--
-- Name: datasets datasets_tenant_id_fkey; Type: FK CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.datasets
    ADD CONSTRAINT datasets_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenant_test_company.tenants(id) ON DELETE CASCADE;


--
-- Name: document_chunks document_chunks_dataset_id_fkey; Type: FK CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.document_chunks
    ADD CONSTRAINT document_chunks_dataset_id_fkey FOREIGN KEY (dataset_id) REFERENCES tenant_test_company.datasets(id) ON DELETE CASCADE;


--
-- Name: document_chunks document_chunks_document_id_fkey; Type: FK CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.document_chunks
    ADD CONSTRAINT document_chunks_document_id_fkey FOREIGN KEY (document_id) REFERENCES tenant_test_company.documents(id) ON DELETE CASCADE;


--
-- Name: document_chunks document_chunks_tenant_id_fkey; Type: FK CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.document_chunks
    ADD CONSTRAINT document_chunks_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenant_test_company.tenants(id) ON DELETE CASCADE;


--
-- Name: document_chunks document_chunks_user_id_fkey; Type: FK CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.document_chunks
    ADD CONSTRAINT document_chunks_user_id_fkey FOREIGN KEY (user_id) REFERENCES tenant_test_company.users(id) ON DELETE CASCADE;


--
-- Name: documents documents_dataset_id_fkey; Type: FK CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.documents
    ADD CONSTRAINT documents_dataset_id_fkey FOREIGN KEY (dataset_id) REFERENCES tenant_test_company.datasets(id) ON DELETE CASCADE;


--
-- Name: documents documents_tenant_id_fkey; Type: FK CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.documents
    ADD CONSTRAINT documents_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenant_test_company.tenants(id) ON DELETE CASCADE;


--
-- Name: documents documents_user_id_fkey; Type: FK CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.documents
    ADD CONSTRAINT documents_user_id_fkey FOREIGN KEY (user_id) REFERENCES tenant_test_company.users(id) ON DELETE CASCADE;


--
-- Name: document_summaries document_summaries_document_id_fkey; Type: FK CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.document_summaries
    ADD CONSTRAINT document_summaries_document_id_fkey FOREIGN KEY (document_id) REFERENCES tenant_test_company.documents(id) ON DELETE CASCADE;


--
-- Name: document_summaries document_summaries_user_id_fkey; Type: FK CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.document_summaries
    ADD CONSTRAINT document_summaries_user_id_fkey FOREIGN KEY (user_id) REFERENCES tenant_test_company.users(id) ON DELETE CASCADE;


--
-- Name: messages messages_conversation_id_fkey; Type: FK CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.messages
    ADD CONSTRAINT messages_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES tenant_test_company.conversations(id) ON DELETE CASCADE;


--
-- Name: messages messages_user_id_fkey; Type: FK CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.messages
    ADD CONSTRAINT messages_user_id_fkey FOREIGN KEY (user_id) REFERENCES tenant_test_company.users(id) ON DELETE CASCADE;


--
-- Name: subagent_executions subagent_executions_conversation_id_fkey; Type: FK CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.subagent_executions
    ADD CONSTRAINT subagent_executions_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES tenant_test_company.conversations(id) ON DELETE CASCADE;


--
-- Name: subagent_executions subagent_executions_parent_agent_id_fkey; Type: FK CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.subagent_executions
    ADD CONSTRAINT subagent_executions_parent_agent_id_fkey FOREIGN KEY (parent_agent_id) REFERENCES tenant_test_company.agents(id) ON DELETE CASCADE;


--
-- Name: task_classifications task_classifications_conversation_id_fkey; Type: FK CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.task_classifications
    ADD CONSTRAINT task_classifications_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES tenant_test_company.conversations(id) ON DELETE CASCADE;


--
-- Name: team_memberships team_memberships_team_id_fkey; Type: FK CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.team_memberships
    ADD CONSTRAINT team_memberships_team_id_fkey FOREIGN KEY (team_id) REFERENCES tenant_test_company.teams(id) ON DELETE CASCADE;


--
-- Name: team_memberships team_memberships_user_id_fkey; Type: FK CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.team_memberships
    ADD CONSTRAINT team_memberships_user_id_fkey FOREIGN KEY (user_id) REFERENCES tenant_test_company.users(id) ON DELETE CASCADE;


--
-- Name: team_resource_shares team_resource_shares_shared_by_fkey; Type: FK CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.team_resource_shares
    ADD CONSTRAINT team_resource_shares_shared_by_fkey FOREIGN KEY (shared_by) REFERENCES tenant_test_company.users(id);


--
-- Name: team_resource_shares team_resource_shares_team_id_fkey; Type: FK CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.team_resource_shares
    ADD CONSTRAINT team_resource_shares_team_id_fkey FOREIGN KEY (team_id) REFERENCES tenant_test_company.teams(id) ON DELETE CASCADE;


--
-- Name: teams teams_owner_id_fkey; Type: FK CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.teams
    ADD CONSTRAINT teams_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES tenant_test_company.users(id) ON DELETE CASCADE;


--
-- Name: teams teams_tenant_id_fkey; Type: FK CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.teams
    ADD CONSTRAINT teams_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenant_test_company.tenants(id) ON DELETE CASCADE;


--
-- Name: users users_tenant_id_fkey; Type: FK CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.users
    ADD CONSTRAINT users_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenant_test_company.tenants(id) ON DELETE CASCADE;


--
-- Name: workflow_executions workflow_executions_conversation_id_fkey; Type: FK CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.workflow_executions
    ADD CONSTRAINT workflow_executions_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES tenant_test_company.conversations(id);


--
-- Name: workflow_executions workflow_executions_parent_agent_id_fkey; Type: FK CONSTRAINT; Schema: tenant_test_company; Owner: -
--

ALTER TABLE ONLY tenant_test_company.workflow_executions
    ADD CONSTRAINT workflow_executions_parent_agent_id_fkey FOREIGN KEY (parent_agent_id) REFERENCES tenant_test_company.agents(id);


--
-- Name: document_chunks document_chunks_user_access; Type: POLICY; Schema: tenant_test_company; Owner: -
--

CREATE POLICY document_chunks_user_access ON tenant_test_company.document_chunks USING (true);


--
-- Name: documents documents_user_access; Type: POLICY; Schema: tenant_test_company; Owner: -
--

CREATE POLICY documents_user_access ON tenant_test_company.documents USING (((current_setting('app.current_user_id'::text, true) = 'bypass'::text) OR (current_setting('app.current_user_id'::text, true) IS NULL) OR (current_setting('app.current_user_id'::text, true) = ''::text) OR (user_id = (current_setting('app.current_user_id'::text, true))::uuid)));


--
-- PostgreSQL database dump complete
--

--
-- Grant permissions to gt2_tenant_user for application access
-- This must run after all tables/sequences are created
--

GRANT USAGE ON SCHEMA tenant_test_company TO gt2_tenant_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA tenant_test_company TO gt2_tenant_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA tenant_test_company TO gt2_tenant_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA tenant_test_company TO gt2_tenant_user;

-- Set default privileges for any future objects created in this schema
ALTER DEFAULT PRIVILEGES IN SCHEMA tenant_test_company GRANT ALL ON TABLES TO gt2_tenant_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA tenant_test_company GRANT ALL ON SEQUENCES TO gt2_tenant_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA tenant_test_company GRANT EXECUTE ON FUNCTIONS TO gt2_tenant_user;

-- Log completion
DO $$
BEGIN
    RAISE NOTICE '=== GT 2.0 TENANT SCHEMA PERMISSIONS ===';
    RAISE NOTICE 'Granted all privileges on tenant_test_company to gt2_tenant_user';
    RAISE NOTICE '=========================================';
END $$;

