-- Análise de cada comunicação no modo sombra (Fluxo 1, etapas 2 e 3).
-- RLS ligado e sem políticas, como as demais tabelas.

create table public.analises (
    comunicacao_id text primary key references public.comunicacoes (id) on delete cascade,
    fora_de_escopo text,             -- motivo da exclusão; nulo quando entra no Fluxo 1
    classe text,
    polo_cliente text,
    ato text,
    trecho_prazo text,               -- trecho do texto que fixa o prazo, se houver
    prazo_dias integer,
    fundamento_prazo text,
    publicacao date,
    inicio date,
    seguranca date,
    vencimento date,
    avisos jsonb not null default '[]'::jsonb,
    resumo text,
    modelo text,
    erro text,
    analisada_em timestamptz not null default now()
);

create index analises_seguranca_idx on public.analises (seguranca);

alter table public.analises enable row level security;

comment on table public.analises is 'Classificação e prazo calculado de cada comunicação (modo sombra: nada é lançado no Legal One).';
