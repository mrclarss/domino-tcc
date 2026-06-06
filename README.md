# 🧪 Dominó de Química Orgânica

![Protótipo pelo figma](https://www.figma.com/design/EbQO31uuK0yGDlaYnXwUbE/Apar%C3%AAncia---domin%C3%B3?m=auto&t=CWX8eATJcmZJ4YJw-6)
![Badge Licença](https://img.shields.io/badge/Licen%C3%A7a-MIT-green)

Um projeto pedagógico e interativo que transforma o clássico jogo de dominó em uma ferramenta de aprendizado para a Química Orgânica. O objetivo é conectar fórmulas estruturais, nomes IUPAC e funções orgânicas de forma divertida e dinâmica.

---

## 📌 Índice

- [Sobre o Projeto](#-sobre-o-projeto)
- [Como Jogar](#-como-jogar)
- [Regras de Associação](#-regras-de-associa%C3%A7%C3%A3o)
- [Tecnologias Utilizadas](#-tecnologias-utilizadas)
- [Como Executar o Projeto](#-como-executar-o-projeto)
- [Contribuintes](#-contribuintes)
- [Licença](#-licen%C3%A7a)

---

## 🔬 Sobre o Projeto

Este projeto foi desenvolvido com o intuito de mitigar as dificuldades no aprendizado de funções orgânicas e nomenclatura IUPAC. Em vez dos tradicionais pontos do dominó, as peças contêm representações químicas que precisam ser combinadas corretamente.

> **Exemplo:** Uma ponta da peça possui a estrutura do *Etanol* e a outra ponta possui o nome escrito *Propano*. O jogador deve conectar a estrutura do Etanol à palavra "Álcool" ou à fórmula molecular correspondente em outra peça.

---

## 🎮 Como Jogar

1. **Distribuição:** Cada jogador recebe 7 peças (baseado em 2 a 4 jogadores).
2. **Início:** O jogador com a peça de maior "peso" (ex: uma peça dupla de Benzeno) começa.
3. **Dinâmica:** Os jogadores, alternadamente, devem encaixar uma peça de sua mão que corresponda quimicamente com a função químicamente correta à molécula.
4. **Vitória:** Vence quem conseguir bolar a estratégia certa e descarregar todas as peças primeiro.

---

## 📐 Regras de Associação (Como as peças se conectam)

O jogo valida o conhecimento através de três pilares de associação:

| Tipo de Conexão | Lado A (Exemplo) | Lado B (Exemplo) | Correspondência |
| :--- | :--- | :--- | :--- |
| **Nomenclatura ⇄ Estrutura** | `CH3-OH` | Metanol | **Válida** (Estrutura e Nome) |
| **Função ⇄ Estrutura** | `CH3-COOH` | Ácido Carboxílico | **Válida** (Grupo Funcional) |
| **Fórmula ⇄ Nomenclatura** | `C3H8` | Propano | **Válida** (Fórmula Molecular) |

---

## 🛠️ Tecnologias Utilizadas

*(Escolha/Adapte as tecnologias abaixo caso seu projeto seja um software, site ou app)*

* **Linguagem:** Python 
* **Interface Gráfica:** Pygame 
* **Design das Peças:** Figma 

---

## 🚀 Como Executar o Projeto

### Pré-requisitos
Antes de começar, você vai precisar ter instalado em sua máquina o [Git](https://git-scm.com) e o [Python](https://www.python.org/) (ou Node.js, dependendo do seu projeto).

### Passo a Passo

```bash
# Clone este repositório
$ git clone [https://github.com/seu-usuario/domino-quimica-organica.git](https://github.com/seu-usuario/domino-quimica-organica.git)

# Acesse a pasta do projeto
$ cd domino-quimica-organica

# Instale as dependências (se houver)
$ pip install -r requirements.txt

# Execute a aplicação
$ python main.py
