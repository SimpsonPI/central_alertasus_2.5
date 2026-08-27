create table regulacoes (
  id serial primary key,
  usuario_id bigint not null,
  cartao_sus varchar(15) not null,
  nome_completo text not null,
  celular varchar(20),
  data_nascimento date,
  cbo varchar(20),
  procedimento text not null,
  status text default 'Pendente',
  criado_em timestamp default now()
);

create table chamados (
  id serial primary key,
  usuario_id bigint not null,
  mensagem_texto text not null,
  resposta text default null,
  respondido boolean default false,
  criado_em timestamp default now()
);