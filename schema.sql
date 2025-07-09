--
-- PostgreSQL database dump
--

-- Dumped from database version 16.9
-- Dumped by pg_dump version 16.5

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

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: clock_session; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.clock_session (
    id integer NOT NULL,
    user_id integer NOT NULL,
    job_id integer NOT NULL,
    labor_activity_id integer NOT NULL,
    clock_in timestamp without time zone NOT NULL,
    clock_out timestamp without time zone,
    notes text,
    is_active boolean,
    created_at timestamp without time zone,
    clock_in_latitude double precision,
    clock_in_longitude double precision,
    clock_in_accuracy double precision,
    clock_out_latitude double precision,
    clock_out_longitude double precision,
    clock_out_accuracy double precision,
    clock_in_distance_mi double precision,
    clock_out_distance_mi double precision
);


--
-- Name: clock_session_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.clock_session_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: clock_session_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.clock_session_id_seq OWNED BY public.clock_session.id;


--
-- Name: job; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.job (
    id integer NOT NULL,
    job_code character varying(20) NOT NULL,
    description character varying(255) NOT NULL,
    status character varying(20),
    trade_type character varying(50),
    foreman_id integer,
    created_at timestamp without time zone,
    location character varying(255),
    latitude double precision,
    longitude double precision
);


--
-- Name: job_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.job_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: job_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.job_id_seq OWNED BY public.job.id;


--
-- Name: job_workers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.job_workers (
    job_id integer NOT NULL,
    user_id integer NOT NULL,
    assigned_at timestamp without time zone
);


--
-- Name: labor_activity; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.labor_activity (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    trade_category character varying(50) NOT NULL,
    created_at timestamp without time zone,
    trade_id integer,
    is_active boolean DEFAULT true
);


--
-- Name: labor_activity_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.labor_activity_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: labor_activity_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.labor_activity_id_seq OWNED BY public.labor_activity.id;


--
-- Name: time_entry; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.time_entry (
    id integer NOT NULL,
    user_id integer NOT NULL,
    job_id integer NOT NULL,
    labor_activity_id integer NOT NULL,
    date date NOT NULL,
    hours double precision NOT NULL,
    notes text,
    approved boolean,
    approved_by integer,
    approved_at timestamp without time zone,
    created_at timestamp without time zone
);


--
-- Name: time_entry_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.time_entry_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: time_entry_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.time_entry_id_seq OWNED BY public.time_entry.id;


--
-- Name: trade; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.trade (
    id integer NOT NULL,
    name character varying(50) NOT NULL,
    is_active boolean,
    created_at timestamp without time zone
);


--
-- Name: trade_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.trade_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: trade_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.trade_id_seq OWNED BY public.trade.id;


--
-- Name: user; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."user" (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    email character varying(120) NOT NULL,
    password_hash character varying(256) NOT NULL,
    role character varying(20) NOT NULL,
    created_at timestamp without time zone,
    use_clock_in boolean DEFAULT false,
    burden_rate numeric(10,2)
);


--
-- Name: user_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_id_seq OWNED BY public."user".id;


--
-- Name: weekly_approval_lock; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.weekly_approval_lock (
    id integer NOT NULL,
    user_id integer NOT NULL,
    job_id integer NOT NULL,
    week_start date NOT NULL,
    approved_by integer NOT NULL,
    approved_at timestamp without time zone
);


--
-- Name: weekly_approval_lock_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.weekly_approval_lock_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: weekly_approval_lock_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.weekly_approval_lock_id_seq OWNED BY public.weekly_approval_lock.id;


--
-- Name: clock_session id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clock_session ALTER COLUMN id SET DEFAULT nextval('public.clock_session_id_seq'::regclass);


--
-- Name: job id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.job ALTER COLUMN id SET DEFAULT nextval('public.job_id_seq'::regclass);


--
-- Name: labor_activity id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.labor_activity ALTER COLUMN id SET DEFAULT nextval('public.labor_activity_id_seq'::regclass);


--
-- Name: time_entry id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.time_entry ALTER COLUMN id SET DEFAULT nextval('public.time_entry_id_seq'::regclass);


--
-- Name: trade id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trade ALTER COLUMN id SET DEFAULT nextval('public.trade_id_seq'::regclass);


--
-- Name: user id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."user" ALTER COLUMN id SET DEFAULT nextval('public.user_id_seq'::regclass);


--
-- Name: weekly_approval_lock id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weekly_approval_lock ALTER COLUMN id SET DEFAULT nextval('public.weekly_approval_lock_id_seq'::regclass);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: clock_session clock_session_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clock_session
    ADD CONSTRAINT clock_session_pkey PRIMARY KEY (id);


--
-- Name: job job_job_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.job
    ADD CONSTRAINT job_job_code_key UNIQUE (job_code);


--
-- Name: job job_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.job
    ADD CONSTRAINT job_pkey PRIMARY KEY (id);


--
-- Name: job_workers job_workers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.job_workers
    ADD CONSTRAINT job_workers_pkey PRIMARY KEY (job_id, user_id);


--
-- Name: labor_activity labor_activity_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.labor_activity
    ADD CONSTRAINT labor_activity_pkey PRIMARY KEY (id);


--
-- Name: time_entry time_entry_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.time_entry
    ADD CONSTRAINT time_entry_pkey PRIMARY KEY (id);


--
-- Name: trade trade_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trade
    ADD CONSTRAINT trade_name_key UNIQUE (name);


--
-- Name: trade trade_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trade
    ADD CONSTRAINT trade_pkey PRIMARY KEY (id);


--
-- Name: weekly_approval_lock unique_weekly_approval; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weekly_approval_lock
    ADD CONSTRAINT unique_weekly_approval UNIQUE (user_id, job_id, week_start);


--
-- Name: user user_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."user"
    ADD CONSTRAINT user_email_key UNIQUE (email);


--
-- Name: user user_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."user"
    ADD CONSTRAINT user_pkey PRIMARY KEY (id);


--
-- Name: weekly_approval_lock weekly_approval_lock_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weekly_approval_lock
    ADD CONSTRAINT weekly_approval_lock_pkey PRIMARY KEY (id);


--
-- Name: ux_clock_session_one_active_per_user; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_clock_session_one_active_per_user ON public.clock_session USING btree (user_id) WHERE ((clock_out IS NULL) AND (is_active = true));


--
-- Name: clock_session clock_session_job_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clock_session
    ADD CONSTRAINT clock_session_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.job(id);


--
-- Name: clock_session clock_session_labor_activity_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clock_session
    ADD CONSTRAINT clock_session_labor_activity_id_fkey FOREIGN KEY (labor_activity_id) REFERENCES public.labor_activity(id);


--
-- Name: clock_session clock_session_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clock_session
    ADD CONSTRAINT clock_session_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: labor_activity fk_labor_activity_trade; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.labor_activity
    ADD CONSTRAINT fk_labor_activity_trade FOREIGN KEY (trade_id) REFERENCES public.trade(id);


--
-- Name: job job_foreman_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.job
    ADD CONSTRAINT job_foreman_id_fkey FOREIGN KEY (foreman_id) REFERENCES public."user"(id);


--
-- Name: job_workers job_workers_job_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.job_workers
    ADD CONSTRAINT job_workers_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.job(id);


--
-- Name: job_workers job_workers_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.job_workers
    ADD CONSTRAINT job_workers_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: time_entry time_entry_approved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.time_entry
    ADD CONSTRAINT time_entry_approved_by_fkey FOREIGN KEY (approved_by) REFERENCES public."user"(id);


--
-- Name: time_entry time_entry_job_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.time_entry
    ADD CONSTRAINT time_entry_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.job(id);


--
-- Name: time_entry time_entry_labor_activity_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.time_entry
    ADD CONSTRAINT time_entry_labor_activity_id_fkey FOREIGN KEY (labor_activity_id) REFERENCES public.labor_activity(id);


--
-- Name: time_entry time_entry_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.time_entry
    ADD CONSTRAINT time_entry_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: weekly_approval_lock weekly_approval_lock_approved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weekly_approval_lock
    ADD CONSTRAINT weekly_approval_lock_approved_by_fkey FOREIGN KEY (approved_by) REFERENCES public."user"(id);


--
-- Name: weekly_approval_lock weekly_approval_lock_job_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weekly_approval_lock
    ADD CONSTRAINT weekly_approval_lock_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.job(id);


--
-- Name: weekly_approval_lock weekly_approval_lock_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weekly_approval_lock
    ADD CONSTRAINT weekly_approval_lock_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- PostgreSQL database dump complete
--

