# Emulador de Rede Mininet com Topologia GML e Controlador ONOS

Este projeto contém um script Python para emular topologias de rede complexas no Mininet, lendo a estrutura de um arquivo `.gml` local. O principal objetivo é conectar esta rede emulada a um controlador ONOS para visualização e gerenciamento centralizado.

O script foi desenvolvido e adaptado para funcionar em um ambiente de máquina virtual (VM) ONOS mais antigo, que possui um ecossistema baseado em **Python 2**.

## Arquitetura da Solução

1.  Um **script Python** atua como o orquestrador.
2.  A biblioteca **NetworkX** é usada para ler e analisar o arquivo de topologia `.gml`.
3.  A biblioteca **Mininet** cria os switches, hosts e links virtuais para emular a rede.
4.  Cada switch OpenFlow na rede Mininet é configurado para se conectar ao **controlador ONOS** como seu cérebro.
5.  A **GUI do ONOS** é usada para visualizar a topologia da rede em tempo real.

![Arquitetura da Solução](https://i.imgur.com/uGg0iNq.png)

## Pré-requisitos de Ambiente

**ATENÇÃO:** Este projeto foi configurado para um ambiente muito específico.

* **Máquina Virtual:** Desenvolvido em uma VM ONOS (baseada em Ubuntu 16.04 ou similar).
* **ONOS:** Uma instância do ONOS deve estar rodando na VM.
* **Interpretador Python:** **Python 2.7**. O script é incompatível com Python 3 devido às dependências do Mininet neste ambiente.
* **Mininet:** Uma versão compatível com Python 2, geralmente localizada em `/home/sdn/mininet`.
* **PIP:** O gerenciador de pacotes `pip` para Python 2.

## 1. Configuração do Ambiente

Siga estes passos para preparar a sua VM.

### 1.1 Preparando o Mininet

1.  **Clone o repositório:**
    ```bash
    git clone <url-do-seu-repositorio>
    cd <nome-do-seu-repositorio>
    ```

2.  **Verifique e Repare o `pip` (Recomendado):**
    Para evitar problemas de instalação, é recomendado reinstalar o `pip` para Python 2:
    ```bash
    sudo apt-get update
    sudo apt-get install --reinstall python-pip
    ```

3.  **Instale as dependências Python:**
    Use o arquivo `requirements.txt` para instalar a versão exata do NetworkX compatível com Python 2:
    ```bash
    sudo pip install -r requirements.txt
    ```

### 1.2 Preparando o ONOS

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
    Coloque seu arquivo de topologia (ex: `polska.gml`) dentro da pasta `src/`.

2.  **Edite o Script:**
    Abra o arquivo `src/run_tata_mininet.py` e altere a variável `LOCAL_GML_FILE` para corresponder ao nome do seu arquivo:
    ```python
    # Altere esta linha para o nome do seu arquivo
    LOCAL_GML_FILE = 'polska.gml' 
    ```

## 3. Execução e Visualização

1.  **Navegue até o diretório do script:**
    ```bash
    cd src
    ```

2.  **Execute o script principal:**
    Use `sudo` e o interpretador `python` (não `python3`).
    ```bash
    sudo python run_tata_mininet.py
    ```
    O script irá iniciar o Mininet, e os switches se conectarão ao ONOS.

3.  **Visualize na GUI do ONOS:**
    * Volte para a janela do navegador com a interface do ONOS.
    * Vá para a tela de **Topologia** (ícone de rede na barra lateral).
    * A topologia da sua rede aparecerá na tela.
    * **Dica:** Pressione a tecla `H` para mostrar/ocultar os hosts e `L` para mostrar/ocultar os nomes dos dispositivos.

## Notas Técnicas Importantes

* **Python 2 vs. 3:** A escolha pelo Python 2 é uma restrição imposta pela versão do Mininet presente na VM.
* **`sudo` e `PYTHONPATH`:** O script adiciona `sys.path.append('/home/sdn/mininet')` para contornar um problema onde `sudo` não consegue localizar a biblioteca Mininet.
* **Conexão ONOS:** O script está configurado para se conectar ao ONOS em `127.0.0.1:6653`. Este endereço funciona pois o Mininet e o ONOS estão na mesma VM.