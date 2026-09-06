-- =============================================================================
-- Wathiq — 11. Privileges
--
-- Run last, and re-run after every migration that adds objects.
--
-- This file is where NFR-4.6 stops being a promise. The application role is
-- granted INSERT and SELECT on the audit log and nothing else; no code path,
-- no ORM callback, and no compromised credential can rewrite history, because
-- the privilege to do so was never granted.
-- =============================================================================

-- Start from zero. PUBLIC gets CREATE on `public` by default in older versions
-- and USAGE broadly; neither is wanted here.
revoke all on schema app, knowledge, ops, audit from public;
revoke all on all tables in schema app, knowledge, ops, audit from public;

-- -----------------------------------------------------------------------------
-- wathiq_migrator — owns the schema, runs migrations. Not used by the app.
-- -----------------------------------------------------------------------------
grant usage, create on schema app, knowledge, ops, audit to wathiq_migrator;
grant all on all tables    in schema app, knowledge, ops, audit to wathiq_migrator;
grant all on all sequences in schema app, knowledge, ops, audit to wathiq_migrator;
grant all on all functions in schema app, knowledge, ops, audit to wathiq_migrator;

-- -----------------------------------------------------------------------------
-- wathiq_app — the Laravel API. Full DML on business data, append-only on audit.
-- -----------------------------------------------------------------------------
grant usage on schema app, knowledge, ops, audit to wathiq_app;

grant select, insert, update, delete on all tables in schema app  to wathiq_app;
grant select, insert, update, delete on all tables in schema ops  to wathiq_app;
grant usage, select on all sequences in schema app, ops to wathiq_app;
grant execute on all functions in schema app to wathiq_app;

-- The knowledge base is administered through the app (FR-12.1 .. FR-12.5) but
-- embeddings are written only by the AI service.
grant select, insert, update, delete on knowledge.sources, knowledge.documents, knowledge.kb_versions to wathiq_app;
grant select on knowledge.chunks to wathiq_app;

-- ***** The NFR-4.6 boundary *****
grant select, insert on audit.audit_logs to wathiq_app;
revoke update, delete, truncate on audit.audit_logs from wathiq_app;
grant usage, select on all sequences in schema audit to wathiq_app;

-- Append-only tables elsewhere. The triggers already reject mutation; removing
-- the privilege as well means the attempt fails before a trigger has to fire,
-- and makes the intent legible in \dp output.
revoke update, delete on
    app.contract_versions,
    app.contract_clauses,
    app.contract_status_history,
    app.signatures,
    app.contract_seals,
    app.wallet_entries,
    app.payment_events,
    app.contract_executions,
    app.receipts
from wathiq_app;

-- -----------------------------------------------------------------------------
-- wathiq_ai — the FastAPI service. Knowledge base only.
--
-- It receives contract text in the job payload over HTTP, so it has no reason
-- to read app.contracts — and now no ability to. If the AI service is ever
-- compromised, the blast radius is the public legal corpus, not the contracts.
-- -----------------------------------------------------------------------------
grant usage on schema knowledge to wathiq_ai;
grant select, insert, update, delete on all tables in schema knowledge to wathiq_ai;
grant usage, select on all sequences in schema knowledge to wathiq_ai;

-- Just enough of `app` to resolve jurisdictions and report job outcomes.
grant usage on schema app to wathiq_ai;
grant select on app.jurisdictions, app.countries to wathiq_ai;
grant select, update on app.ai_jobs to wathiq_ai;
grant execute on function app.uuid_generate_v7() to wathiq_ai;

-- Explicitly denied, and worth stating rather than leaving implicit.
revoke all on app.contracts, app.contract_versions, app.contract_clauses,
              app.users, app.user_profiles, app.identity_documents,
              app.payments, app.wallets, app.wallet_entries, app.signatures
from wathiq_ai;

-- -----------------------------------------------------------------------------
-- wathiq_readonly — analytics, BI, on-call inspection.
-- -----------------------------------------------------------------------------
grant usage on schema app, knowledge, audit to wathiq_readonly;
grant select on all tables in schema app, knowledge, audit to wathiq_readonly;

-- KYC documents, deeds and session tokens are not analytics data.
revoke select on app.identity_documents, app.ownership_documents, app.user_sessions,
                 app.one_time_tokens
from wathiq_readonly;

-- -----------------------------------------------------------------------------
-- Defaults for objects created later
--
-- Without these, every future migration silently creates a table the
-- application cannot read, and the failure appears at runtime rather than at
-- deploy time.
-- -----------------------------------------------------------------------------
alter default privileges for role wathiq_migrator in schema app, ops
    grant select, insert, update, delete on tables to wathiq_app;
alter default privileges for role wathiq_migrator in schema app, ops
    grant usage, select on sequences to wathiq_app;
alter default privileges for role wathiq_migrator in schema app
    grant execute on functions to wathiq_app;

alter default privileges for role wathiq_migrator in schema knowledge
    grant select, insert, update, delete on tables to wathiq_ai;

alter default privileges for role wathiq_migrator in schema app, knowledge
    grant select on tables to wathiq_readonly;

alter default privileges for role wathiq_migrator in schema audit
    grant select, insert on tables to wathiq_app;

-- -----------------------------------------------------------------------------
-- Verification
--
-- Run in CI after migrating. A green migration that quietly granted the app
-- DELETE on the audit log is worse than a failed one.
-- -----------------------------------------------------------------------------
create or replace function app.assert_privilege_invariants()
returns void
language plpgsql
as $$
begin
    if has_table_privilege('wathiq_app', 'audit.audit_logs', 'UPDATE')
       or has_table_privilege('wathiq_app', 'audit.audit_logs', 'DELETE') then
        raise exception 'NFR-4.6 violated: wathiq_app holds UPDATE or DELETE on audit.audit_logs'
            using errcode = 'restrict_violation';
    end if;

    if has_table_privilege('wathiq_ai', 'app.contracts', 'SELECT') then
        raise exception 'wathiq_ai can read app.contracts; the knowledge-schema boundary is broken'
            using errcode = 'restrict_violation';
    end if;

    if has_table_privilege('wathiq_readonly', 'app.identity_documents', 'SELECT') then
        raise exception 'wathiq_readonly can read KYC documents'
            using errcode = 'restrict_violation';
    end if;

    perform app.assert_no_float_columns();
end;
$$;
