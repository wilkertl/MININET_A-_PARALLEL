# Emulador de Rede Mininet com Topologia GML e Controlador ONOS

Este projeto contém um script Python para emular topologias de rede complexas no Mininet, lendo a estrutura de um arquivo `.gml` local. O principal objetivo é conectar esta rede emulada a um controlador ONOS para visualização e gerenciamento centralizado.

O script foi desenvolvido e adaptado para funcionar em um ambiente moderno baseado em **Python 3**.

## Arquitetura da Solução

1.  Um **script Python** atua como o orquestrador.
2.  A biblioteca **NetworkX** é usada para ler e analisar o arquivo de topologia `.gml`.
3.  A biblioteca **Mininet** cria os switches, hosts e links virtuais para emular a rede.
4.  Cada switch OpenFlow na rede Mininet é configurado para se conectar ao **controlador ONOS** como seu cérebro.
5.  A **GUI do ONOS** é usada para visualizar a topologia da rede em tempo real.

![Arquitetura da Solução](https://i.imgur.com/uGg0iNq.png)

## Pré-requisitos de Ambiente

**ATENÇÃO:** Este projeto requer Python 3 e um ambiente moderno.

* **Sistema Operacional:** Ubuntu 18.04+ ou similar
* **ONOS:** Uma instância do ONOS deve estar rodando na máquina.
* **Interpretador Python:** **Python 3.8+**. O script é otimizado para Python 3.
* **Mininet:** Uma versão compatível com Python 3.
* **PIP:** O gerenciador de pacotes `pip` para Python 3.

## 1. Configuração do Ambiente

Siga estes passos para preparar o seu ambiente.

### 1.1 Configuração Rápida

Execute o script de setup automatizado:

```bash
# Clone o repositório
git clone <url-do-seu-repositorio>
cd <nome-do-seu-repositorio>

# Execute o setup
chmod +x setup_python3.sh
./setup_python3.sh
```

### 1.2 Configuração Manual

1.  **Clone o repositório:**
    ```bash
    git clone <url-do-seu-repositorio>
    cd <nome-do-seu-repositorio>
    ```

2.  **Crie um ambiente virtual:**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3.  **Instale as dependências Python:**
    ```bash
    pip install -r requirements.txt
    ```

### 1.3 Preparando o ONOS

1.  **Acesse a GUI do ONOS:** Em seu computador principal, abra um navegador e acesse `http://<IP_DA_SUA_VM>:8181/onos/ui`. Faça login com `onos` / `rocks`.

2.  **Ative o App OpenFlow (Passo Crucial):** O ONOS só atuará como controlador OpenFlow se a aplicação correspondente estiver ativa. Verifique e ative-a:
    ```bash
    # Conecte-se ao console do ONOS
    ssh -p 8101 onos@localhost
    # A senha é 'rocks'

    # Dentro do console onos>, verifique os apps ativos
    apps -a -s

    # Se 'org.onosproject.openflow' não estiver na lista, ative-o:
    app activate org.onosproject.openflow

    # Saia do console
    logout
    ```

## 2. Configuração do Script

1.  **Adicione seu Arquivo GML:**
    Coloque seu arquivo de topologia (ex: `tata_nld.gml`) dentro da pasta `src/`.

2.  **Edite o Script (se necessário):**
    O script já está configurado para usar `tata_nld.gml`. Se quiser usar outro arquivo, edite a variável `LOCAL_GML_FILE` em `src/run_tata_mininet.py`:
    ```python
    # Altere esta linha para o nome do seu arquivo
    LOCAL_GML_FILE = 'seu_arquivo.gml' 
    ```

## 3. Execução e Visualização

1.  **Ative o ambiente virtual (se usando):**
    ```bash
    source .venv/bin/activate
    ```

2.  **Execute o script principal:**
    Use `sudo` e o interpretador `python3`.
    ```bash
    sudo python3 src/run_tata_mininet.py
    ```
    O script irá iniciar o Mininet, e os switches se conectarão ao ONOS.

3.  **Visualize na GUI do ONOS:**
    * Volte para a janela do navegador com a interface do ONOS.
    * Vá para a tela de **Topologia** (ícone de rede na barra lateral).
    * A topologia da sua rede aparecerá na tela.
    * **Dica:** Pressione a tecla `H` para mostrar/ocultar os hosts e `L` para mostrar/ocultar os nomes dos dispositivos.

## Notas Técnicas Importantes

* **Python 3:** O script foi atualizado para usar Python 3 com todas as suas funcionalidades modernas.
* **Ambiente Virtual:** Recomendamos usar um ambiente virtual para isolar as dependências.
* **Conexão ONOS:** O script está configurado para se conectar ao ONOS em `127.0.0.1:6653`.
* **Compatibilidade:** O script usa `.format()` em vez de f-strings para máxima compatibilidade.

## Solução de Problemas

### Erro de NumPy/NetworkX
Se você encontrar erros relacionados ao NumPy 2.0, execute:
```bash
pip install "numpy<2.0" --break-system-packages
```

### Erro de Permissão
Certifique-se de executar o script com `sudo`:
```bash
sudo python3 src/run_tata_mininet.py
```