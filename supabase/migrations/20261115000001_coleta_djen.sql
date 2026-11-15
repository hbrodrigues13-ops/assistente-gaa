-- Coleta do DJEN (Fluxo 1, etapa 1). Projeto Supabase: assistente-gaa (sa-east-1).
-- RLS ligado e sem políticas: anon e authenticated não leem nem gravam.
-- Só a chave service_role (no .env do computador de Henrique) acessa.

create table public.comunicacoes (
    id text primary key,                 -- identificador da comunicação no DJEN (princípio 5)
    oab text not null,
    disponibilizacao date not null,
    numero_processo text,
    tribunal text,
    bruto jsonb not null,
    coletada_em timestamptz not null default now()
);

create index comunicacoes_disponibilizacao_idx on public.comunicacoes (disponibilizacao);
create index comunicacoes_numero_processo_idx on public.comunicacoes (numero_processo);

create table public.coletas (
    id bigint generated always as identity primary key,
    oab text not null,
    inicio date not null,
    fim date not null,
    executada_em timestamptz not null,
    erro text
);

create index coletas_oab_ok_idx on public.coletas (oab, fim) where erro is null;

alter table public.comunicacoes enable row level security;
alter table public.coletas enable row level security;

comment on table public.comunicacoes is 'Publicações brutas do DJEN por OAB monitorada. Dados de clientes: sigilo profissional e LGPD.';
comment on table public.coletas is 'Registro de cada rodada da coleta do DJEN (sucesso ou erro).';
