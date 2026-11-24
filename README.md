# Vida Longa

**Um experimento sobre quanto tempo daria para viver em um mundo sem doenças — usando dados brasileiros de mortalidade.**

E se câncer, infarto e gripe simplesmente saíssem de cena? Ainda sobrariam trânsito, quedas, afogamentos, violência e aquela dose diária de azar. O Vida Longa cria vidas possíveis a partir de causas externas de morte, congelando o perfil escolhido na idade selecionada.

> Não é uma previsão de vida, não é uma consultoria médica e, infelizmente, não vende a fonte da juventude.

## Ver o experimento

Sirva o projeto localmente:

```bash
python -m http.server
```

Depois abra `http://localhost:8000`.

## Como funciona

Escolha sexo, estado e idade, execute entre 1.000 e 100.000 vidas simuladas e veja:

- uma vida sorteada, até a provável desculpa para o atestado;
- a causa de morte e sua posição na classificação CID-10;
- a distribuição das idades ao morrer;
- as causas externas mais frequentes para o perfil.

O modelo usa uma taxa anual calculada a partir do [SIM](https://dadosabertos.saude.gov.br/dataset/sim), aplica o risco de forma exponencial e escolhe uma causa proporcional ao número de óbitos observados. Quando o corpo fica congelado na idade escolhida, o risco não envelhece junto.

## Capturas de tela

### Perfil

![Seleção de perfil](assets/selection.png)

### Uma vida possível

![Resultado para uma vida](assets/results_person.png)

### Muitas vidas

![Resultado para várias vidas](assets/results_people.png)

## Dados

- [Sistema de Informações sobre Mortalidade — SIM](https://dadosabertos.saude.gov.br/dataset/sim)
- [Dicionário de Dados do SIM 2025](https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SIM/Dicionario_SIM_2025.pdf)
- [Base da Mortalidade Geral 2024](https://dadosabertos.saude.gov.br/dataset/sim/resource/f0bdf83f-708e-4de9-9582-959055844ae9)
- [População estimada — IBGE](https://www.ibge.gov.br/estatisticas/sociais/populacao/9109-populacao-estimada.html)

Os dados originais ficam em `data/`; os CSVs usados pela página são gerados em `data/processed_data/`.

## Estrutura do repositório

```text
vida-longa/
├── index.html
├── README.md
├── assets/
│   ├── selection.png
│   ├── results_person.png
│   └── results_people.png
├── data/
│   ├── Mortalidade_Geral_2024.csv
│   ├── projecoes_2024_tab1_idade_simples.xlsx
│   ├── Dicionario_SIM_2025.pdf
│   └── processed_data/
│       ├── mortality_total.csv
│       └── mortality_by_cause.csv
└── scripts/
    └── process_mortality.py
```

## Inspiração

Este projeto foi inspirado em [PolStats — Life](https://polstats.com/#!/life). Aqui, porém, o experimento usa dados brasileiros: SIM/DATASUS para óbitos por causas externas e estimativas populacionais do IBGE.
