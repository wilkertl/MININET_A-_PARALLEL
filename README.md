# MININET A* PARALLEL

Este projeto implementa uma solução para visualização e análise de topologias de rede usando Mininet e Python.

## Descrição

O projeto permite a visualização de topologias de rede através de um grafo interativo, onde:
- Nós representam switches e hosts
- Arestas representam conexões entre os elementos
- A visualização é gerada a partir de arquivos GML (Graph Modeling Language)

## Requisitos

- Python 3.x
- Dependências Python (instaladas via pip):
  ```
  networkx
  matplotlib
  numpy
  ```

## Instalação

1. Clone o repositório:
   ```bash
   git clone [URL_DO_REPOSITORIO]
   cd MININET_A-_PARALLEL
   ```

2. Crie e ative um ambiente virtual (opcional, mas recomendado):
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   # ou
   .venv\Scripts\activate  # Windows
   ```

3. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

## Uso

Para visualizar uma topologia de rede:

```bash
python src/render_topology.py examples/[arquivo_gml]
```

Por exemplo:
```bash
python src/render_topology.py examples/tata_nld.gml
```

A visualização será salva como `topology_visualization.png` no diretório de exemplos.

## Estrutura do Projeto

```
MININET_A-_PARALLEL/
├── src/                    # Código fonte
│   └── render_topology.py  # Script principal
├── examples/               # Exemplos e recursos
│   ├── tata_nld.gml       # Arquivo de exemplo GML
│   └── topology_visualization.png
├── docs/                   # Documentação
├── tests/                  # Testes
├── requirements.txt        # Dependências
└── README.md              # Este arquivo
```

## Contribuição

Contribuições são bem-vindas! Para contribuir:

1. Faça um fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/nova-feature`)
3. Commit suas mudanças (`git commit -m 'Adiciona nova feature'`)
4. Push para a branch (`git push origin feature/nova-feature`)
5. Abra um Pull Request

## Licença

Este projeto está sob a licença MIT. Veja o arquivo LICENSE para mais detalhes. 