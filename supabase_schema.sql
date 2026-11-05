-- À coller dans Supabase : SQL Editor -> New query -> Run
-- Tables de l'application. La sécurité (RLS) est activée SANS politique : la clé publique (anon) ne peut rien lire ;
-- seul le serveur, avec la clé service_role (secrète), accède aux données.

create table if not exists app_users (
    email text primary key,
    data  jsonb not null default '{}'::jsonb
);

create table if not exists app_comments (
    id   text primary key,
    lien text not null,
    data jsonb not null default '{}'::jsonb
);
create index if not exists app_comments_lien_idx on app_comments (lien);

create table if not exists app_candidatures (
    email text not null,
    cle   text not null,
    primary key (email, cle)
);

-- Clés API : on ne stocke que le hash SHA-256 de la clé (jamais la clé en clair)
create table if not exists app_api_keys (
    key_hash text primary key,
    email    text not null
);
create index if not exists app_api_keys_email_idx on app_api_keys (email);

alter table app_users        enable row level security;
alter table app_comments     enable row level security;
alter table app_candidatures enable row level security;
alter table app_api_keys     enable row level security;

-- Bucket PRIVÉ pour les photos de carte nationale et les selfies
insert into storage.buckets (id, name, public)
values ('kyc', 'kyc', false)
on conflict (id) do update set public = false;
