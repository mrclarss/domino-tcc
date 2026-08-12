import pygame
import sys
import os
import random
import threading
import time
from typing import Optional

# ── Constantes ────────────────────────────────────────────────────────────────
# Resolução em modo retrato (celular). Ajuste se quiser simular outro aparelho,
# ex: 390x844 (iPhone 13), 412x915 (Android médio).
SCREEN_W, SCREEN_H = 400, 820
FPS = 60

# Paleta
C_BG         = (20, 60, 30)
C_FELT       = (28, 80, 42)
C_BONE       = (245, 238, 220)
C_BONE_DARK  = (210, 200, 180)
C_DOT        = (30, 25, 20)
C_DIVIDER    = (160, 148, 128)
C_HIGHLIGHT  = (255, 220, 80)
C_PLAYABLE   = (120, 220, 120)
C_BTN        = (50, 140, 70)
C_BTN_HOV    = (70, 180, 90)
C_BTN_DIS    = (40, 80, 50)
C_BTN_TXT    = (240, 240, 230)
C_TEXT       = (230, 230, 210)
C_TEXT_DIM   = (140, 160, 130)
C_SCORE_BG   = (15, 45, 22)
C_OPPONENT   = (180, 100, 40)
C_PLAYER     = (60, 140, 200)
C_TURN_IND   = (255, 200, 60)

# Tamanho das pedras (reduzido para caber várias por linha na tela estreita)
TILE_W, TILE_H = 40, 76
DOT_R = 4
CORNER_R = 6

# Alvo mínimo de toque recomendado (~44pt no iOS / 48dp no Android)
TOUCH_PAD = 14

pygame.init()


def _font(name, size, bold=False):
    """SysFont pode não existir em todo ambiente mobile/headless; cai no padrão."""
    try:
        return pygame.font.SysFont(name, size, bold=bold)
    except Exception:
        return pygame.font.Font(None, size)


font_lg = _font("segoeui", 22, bold=True)
font_md = _font("segoeui", 17)
font_sm = _font("segoeui", 13)
font_xl = _font("segoeui", 30, bold=True)

DOT_POSITIONS = {
    0: [],
    1: [(0.5, 0.5)],
    2: [(0.25, 0.25), (0.75, 0.75)],
    3: [(0.25, 0.25), (0.5, 0.5), (0.75, 0.75)],
    4: [(0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75)],
    5: [(0.25, 0.25), (0.75, 0.25), (0.5, 0.5), (0.25, 0.75), (0.75, 0.75)],
    6: [(0.25, 0.2), (0.75, 0.2), (0.25, 0.5), (0.75, 0.5), (0.25, 0.8), (0.75, 0.8)],
}

# ── Imagens das faces (0 a 6 pontos) ────────────────────────────────────────────
# Usa os PNGs em assets/face_0.png .. face_6.png. Se a pasta/arquivo não
# existir por algum motivo, cai de volta no desenho com pygame.draw.circle
# (usando DOT_POSITIONS acima), então o jogo nunca quebra por falta de imagem.
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
_face_raw_cache: dict = {}     # value -> Surface original carregada do PNG
_face_scaled_cache: dict = {}  # (value, w, h) -> Surface já redimensionada


def _load_face_raw(value: int):
    if value not in _face_raw_cache:
        path = os.path.join(ASSETS_DIR, f"face_{value}.png")
        try:
            img = pygame.image.load(path)
            try:
                img = img.convert_alpha()
            except pygame.error:
                pass  # ainda sem display inicializado; funciona sem convert_alpha
            _face_raw_cache[value] = img
        except (pygame.error, FileNotFoundError):
            _face_raw_cache[value] = None  # marca como indisponível
    return _face_raw_cache[value]


def _get_scaled_face(value: int, w: int, h: int):
    w = max(1, int(w)); h = max(1, int(h))
    key = (value, w, h)
    if key not in _face_scaled_cache:
        raw = _load_face_raw(value)
        if raw is None:
            _face_scaled_cache[key] = None
        else:
            _face_scaled_cache[key] = pygame.transform.smoothscale(raw, (w, h))
    return _face_scaled_cache[key]


# ── Pedra ──────────────────────────────────────────────────────────────────────
class Tile:
    def __init__(self, a: int, b: int):
        self.a = a
        self.b = b
        self.horizontal = False
        self.flipped = False

    @property
    def left(self):  return self.b if self.flipped else self.a
    @property
    def right(self): return self.a if self.flipped else self.b
    @property
    def top(self):   return self.b if self.flipped else self.a
    @property
    def bottom(self):return self.a if self.flipped else self.b
    @property
    def is_double(self): return self.a == self.b
    @property
    def total(self): return self.a + self.b

    def fits_left(self, value):
        """Encaixa a pedra na PONTA ESQUERDA da mesa: o valor que já
        conecta (igual a `value`) precisa ficar no lado DIREITO da pedra
        (tocando a pedra anterior); o outro valor fica no lado ESQUERDO
        e vira o novo número aberto/jogável."""
        if self.b == value: self.flipped = False; return True  # right=b=value, left=a (novo aberto)
        if self.a == value: self.flipped = True;  return True  # right=a=value, left=b (novo aberto)
        return False

    def fits_right(self, value):
        """Encaixa a pedra na PONTA DIREITA da mesa: o valor que já
        conecta (igual a `value`) precisa ficar no lado ESQUERDO da pedra
        (tocando a pedra anterior); o outro valor fica no lado DIREITO
        e vira o novo número aberto/jogável."""
        if self.a == value: self.flipped = False; return True  # left=a=value, right=b (novo aberto)
        if self.b == value: self.flipped = True;  return True  # left=b=value, right=a (novo aberto)
        return False

    def __repr__(self):
        return f"[{self.a}|{self.b}]"


def draw_tile(surface, tile: Tile, x: int, y: int,
              selected=False, playable=False, face_down=False, alpha=255):
    w = TILE_H if tile.horizontal else TILE_W
    h = TILE_W if tile.horizontal else TILE_H

    surf = pygame.Surface((w, h), pygame.SRCALPHA)

    shadow = pygame.Surface((w + 4, h + 4), pygame.SRCALPHA)
    pygame.draw.rect(shadow, (0, 0, 0, 80), (4, 4, w, h), border_radius=CORNER_R)
    surface.blit(shadow, (x - 2, y - 2))

    border_col = C_HIGHLIGHT if selected else (C_PLAYABLE if playable else C_BONE_DARK)
    border_w   = 3 if (selected or playable) else 1
    pygame.draw.rect(surf, C_BONE, (0, 0, w, h), border_radius=CORNER_R)
    pygame.draw.rect(surf, border_col, (0, 0, w, h), border_w, border_radius=CORNER_R)

    if face_down:
        for i in range(0, w, 8):
            pygame.draw.line(surf, C_BONE_DARK, (i, 0), (i, h), 1)
        for j in range(0, h, 8):
            pygame.draw.line(surf, C_BONE_DARK, (0, j), (w, j), 1)
        surf.set_alpha(alpha)
        surface.blit(surf, (x, y))
        return

    if tile.horizontal:
        mx = w // 2
        pygame.draw.line(surf, C_DIVIDER, (mx, 4), (mx, h - 4), 2)
        _draw_half(surf, tile.top if not tile.flipped else tile.bottom, 0, 0, mx, h)
        _draw_half(surf, tile.bottom if not tile.flipped else tile.top, mx, 0, mx, h)
    else:
        my = h // 2
        pygame.draw.line(surf, C_DIVIDER, (4, my), (w - 4, my), 2)
        _draw_half(surf, tile.top, 0, 0, w, my)
        _draw_half(surf, tile.bottom, 0, my, w, my)

    surf.set_alpha(alpha)
    surface.blit(surf, (x, y))


def _draw_half(surf, value, ox, oy, w, h):
    pad = 5
    img = _get_scaled_face(value, w - 2 * pad, h - 2 * pad)
    if img is not None:
        surf.blit(img, (ox + pad, oy + pad))
        return
    # Fallback: se a imagem não estiver disponível, desenha os pontos
    # do jeito antigo, com pygame.draw.circle.
    for rx, ry in DOT_POSITIONS.get(value, []):
        cx = int(ox + pad + rx * (w - 2 * pad))
        cy = int(oy + pad + ry * (h - 2 * pad))
        pygame.draw.circle(surf, C_DOT, (cx, cy), DOT_R)


def tile_rect(tile: Tile, x: int, y: int) -> pygame.Rect:
    w = TILE_H if tile.horizontal else TILE_W
    h = TILE_W if tile.horizontal else TILE_H
    return pygame.Rect(x, y, w, h)


# ── Jogo (lógica pura) ──────────────────────────────────────────────────────────
class DominoGame:
    """
    Regras seguidas (ver regulamentos.pdf):
    - 2 jogadores, individual (não em dupla), 7 pedras cada, 14 no estoque.
    - Começa quem tiver a pedra 6x6; se ninguém tiver, começa quem tiver a
      maior pedra dupla; se ninguém tiver dupla nenhuma, começa quem tiver
      a pedra de maior soma na mão.
    - Se algum jogador começar com 4 ou mais "carroças" (peças duplas) na
      mão, as pedras são repostas e distribuídas novamente.
    - O jogo (rodada) termina quando alguém "bate" (fica sem pedras) ou
      "tranca" (ninguém consegue jogar mais).
    - Pontuação por rodada (regra dos 6 pontos do regulamento):
        * Batida simples (fechando só uma ponta) ........... 1 ponto
        * Batida de "carroça" (última pedra é dupla) ....... 2 pontos
        * "Lá e lô" (pedra simples que fecha as duas pontas)  3 pontos
        * "Lá e lô de carroça" (dupla que fecha as 2 pontas)  6 pontos
        * Jogo trancado, vitória por menor soma na mão ...... 1 ponto
      Vence a partida (match) quem acumular 6 pontos primeiro.
    """
    NUM_PLAYERS = 2
    HAND_SIZE   = 7
    MAX_DOUBLES_REDEAL = 4  # regra: 4+ carroças na mão -> reparte tudo

    def __init__(self, forced_starter: Optional[int] = None):
        self.reset(forced_starter)

    def reset(self, forced_starter: Optional[int] = None):
        # Distribui as pedras; se algum jogador começar com 4+ carroças
        # (peças duplas), reparte tudo de novo, conforme o regulamento.
        while True:
            all_tiles = [Tile(a, b) for a in range(7) for b in range(a, 7)]
            random.shuffle(all_tiles)
            hands = [[] for _ in range(self.NUM_PLAYERS)]
            for i in range(self.NUM_PLAYERS):
                hands[i] = all_tiles[i * self.HAND_SIZE:(i + 1) * self.HAND_SIZE]
            doubles_ok = all(
                sum(1 for t in h if t.is_double) < self.MAX_DOUBLES_REDEAL
                for h in hands
            )
            if doubles_ok:
                break

        self.hands = hands
        self.boneyard = all_tiles[self.NUM_PLAYERS * self.HAND_SIZE:]
        self.board: list[Tile] = []
        self.left_end:  Optional[int] = None
        self.right_end: Optional[int] = None
        self.passes  = 0
        self.current = forced_starter if forced_starter is not None else self._first_player()
        self.round_starter = self.current
        self.message = ""
        self.game_over = False
        self.winner = -1
        self.win_reason = None        # "domino" | "trancado"
        self.win_bonus_label = None   # rótulo do tipo de batida
        self.round_points = 0         # pontos ganhos nesta rodada

    def _first_player(self):
        # a) Quem tiver a pedra 6x6 sempre começa a partida
        for i, hand in enumerate(self.hands):
            for t in hand:
                if t.a == 6 and t.b == 6:
                    return i
        # b) Senão, quem tiver a maior pedra dupla
        best = -1; player = None
        for i, hand in enumerate(self.hands):
            for t in hand:
                if t.is_double and t.a > best:
                    best = t.a; player = i
        if player is not None:
            return player
        # Ninguém tem pedra dupla: começa quem tiver a pedra de maior soma
        best_total = -1; player = 0
        for i, hand in enumerate(self.hands):
            for t in hand:
                if t.total > best_total:
                    best_total = t.total; player = i
        return player

    def playable_sides(self, tile: Tile):
        sides = []
        if not self.board:
            sides = ["left"]
        else:
            if tile.a == self.left_end or tile.b == self.left_end:
                sides.append("left")
            if tile.a == self.right_end or tile.b == self.right_end:
                sides.append("right")
        return sides

    def play(self, player: int, tile: Tile, side: str) -> bool:
        if player != self.current:
            return False
        sides = self.playable_sides(tile)
        if side not in sides:
            return False

        self.hands[player].remove(tile)
        if not self.board:
            tile.horizontal = tile.is_double
            self.board.append(tile)
            self.left_end  = tile.a
            self.right_end = tile.b
        elif side == "left":
            tile.fits_left(self.left_end)
            tile.horizontal = tile.is_double
            self.board.insert(0, tile)
            self.left_end = tile.left if not tile.horizontal else tile.top
        else:
            tile.fits_right(self.right_end)
            tile.horizontal = tile.is_double
            self.board.append(tile)
            self.right_end = tile.right if not tile.horizontal else tile.bottom

        self.passes = 0
        # `sides` foi calculado ANTES da jogada: se tinha os dois lados
        # disponíveis, essa pedra fechava as duas pontas ("lá e lô").
        if self._check_win(player, tile, sides):
            return True
        self._next_turn()
        return True

    def draw_from_boneyard(self, player: int) -> Optional[Tile]:
        if not self.boneyard:
            return None
        t = self.boneyard.pop()
        self.hands[player].append(t)
        return t

    def pass_turn(self, player: int):
        self.passes += 1
        if self.passes >= self.NUM_PLAYERS:
            self._end_game_by_lock()
        else:
            self._next_turn()

    def _next_turn(self):
        self.current = (self.current + 1) % self.NUM_PLAYERS

    def _check_win(self, player: int, played_tile: Tile, sides_used: list) -> bool:
        if not self.hands[player]:
            self.game_over = True
            self.winner    = player
            self.win_reason = "domino"
            self.round_points, self.win_bonus_label = self._compute_bonus(played_tile, sides_used)
            quem = "Você" if player == 0 else "Computador"
            self.message = f"{quem} bateu! {self.win_bonus_label} (+{self.round_points})"
            return True
        return False

    @staticmethod
    def _compute_bonus(tile: Tile, sides_used: list):
        """Calcula pontos e rótulo da batida, conforme o regulamento."""
        fecha_as_duas = len(sides_used) == 2
        if tile.is_double and fecha_as_duas:
            return 6, "Lá e lô de carroça"
        if tile.is_double:
            return 2, "Carroça"
        if fecha_as_duas:
            return 3, "Lá e lô"
        return 1, "Batida simples"

    def _end_game_by_lock(self):
        self.game_over = True
        self.win_reason = "trancado"
        totals = [sum(t.total for t in h) for h in self.hands]
        if totals[0] == totals[1]:
            self.winner = -1
            self.round_points = 0
            self.win_bonus_label = "Empate"
            self.message = "Jogo fechado — empate! Ninguém pontua."
        else:
            self.winner = totals.index(min(totals))
            self.round_points = 1
            self.win_bonus_label = "Jogo fechado"
            quem = "Você" if self.winner == 0 else "Computador"
            self.message = f"Jogo fechado! {quem} venceu por pontos (+1)"

    def has_playable(self, player: int) -> bool:
        for t in self.hands[player]:
            if self.playable_sides(t):
                return True
        return False

    def computer_move(self):
        hand = self.hands[1]
        for t in sorted(hand, key=lambda x: -x.total):
            sides = self.playable_sides(t)
            if sides:
                self.play(1, t, sides[0])
                return
        drawn = self.draw_from_boneyard(1)
        if drawn:
            sides = self.playable_sides(drawn)
            if sides:
                self.play(1, drawn, sides[0])
                return
        self.pass_turn(1)


# ── Interface mobile ────────────────────────────────────────────────────────────
class UI:
    # ---- Layout vertical em faixas (topo → base) ----
    TOP_BAR_H      = 50   # estoque / turno / placar da partida
    OPP_HAND_H     = 66   # mão do computador (viradas p/ baixo)
    BUTTONS_H      = 64   # barra de botões grandes no rodapé
    HAND_LABEL_H   = 22
    PLAYER_HAND_H  = 100  # mão do jogador

    BOARD_Y0 = TOP_BAR_H + OPP_HAND_H
    BOARD_Y1 = SCREEN_H - BUTTONS_H - HAND_LABEL_H - PLAYER_HAND_H

    BOARD_AREA = pygame.Rect(0, BOARD_Y0, SCREEN_W, BOARD_Y1 - BOARD_Y0)
    HAND_AREA  = pygame.Rect(0, BOARD_Y1, SCREEN_W, HAND_LABEL_H + PLAYER_HAND_H)

    BONEYARD_BTN = pygame.Rect(6, SCREEN_H - BUTTONS_H + 6, SCREEN_W // 2 - 9, BUTTONS_H - 12)
    PASS_BTN     = pygame.Rect(SCREEN_W // 2 + 3, SCREEN_H - BUTTONS_H + 6, SCREEN_W // 2 - 9, BUTTONS_H - 12)

    MATCH_TARGET_POINTS = 6  # regra: dupla/jogador que acumular 6 pontos vence a partida

    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption("Dominó (mobile)")
        self.clock  = pygame.time.Clock()
        self.game   = DominoGame()
        self.selected: Optional[Tile] = None
        self.comp_delay = 0
        self.msg_timer  = 0
        self._hand_rects: dict = {}
        # Estado de arraste (arrastar pedra da mão até a mesa)
        self.dragging_tile: Optional[Tile] = None
        self.drag_pos = (0, 0)
        self.drag_offset = (0, 0)
        self.drag_origin = (0, 0)
        self.drag_moved = False
        # Estado da partida (várias rodadas, pontuação acumulada)
        self.match_scores = [0, 0]
        self.match_over = False
        self.match_winner = -1
        self.round_num = 1
        self.round_scored = False
        self.next_starter: Optional[int] = None  # próxima rodada: outro jogador

    # ── Loop principal ─────────────────────────────────────────────────────────
    def run(self):
        while True:
            dt = self.clock.tick(FPS)
            self._handle_events()
            self._update(dt)
            self._draw()
            pygame.display.flip()

    def _update(self, dt):
        g = self.game
        if not g.game_over and g.current == 1:
            self.comp_delay += 1
            if self.comp_delay >= 60:
                self.comp_delay = 0
                g.computer_move()

        if g.game_over and not self.round_scored:
            self.round_scored = True
            if g.winner != -1:
                self.match_scores[g.winner] += g.round_points
            if max(self.match_scores) >= self.MATCH_TARGET_POINTS:
                self.match_over = True
                self.match_winner = 0 if self.match_scores[0] > self.match_scores[1] else 1
            # regra: rodadas seguintes começam com o jogador seguinte
            # (sentido anti-horário — com 2 jogadores, é sempre o outro)
            self.next_starter = 1 - g.round_starter

    # ── Eventos (mouse E toque) ──────────────────────────────────────────────────
    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    self._start_new_match()
                if event.key == pygame.K_ESCAPE:
                    self.selected = None

            # Toque real em telas touchscreen (Android/iOS/tablets com SDL2)
            if event.type == pygame.FINGERDOWN:
                pos = (event.x * SCREEN_W, event.y * SCREEN_H)
                self._handle_press(pos)
            elif event.type == pygame.FINGERMOTION:
                pos = (event.x * SCREEN_W, event.y * SCREEN_H)
                self._handle_drag(pos)
            elif event.type == pygame.FINGERUP:
                pos = (event.x * SCREEN_W, event.y * SCREEN_H)
                self._handle_release(pos)

            # Mouse (também é o que chega quando o SO traduz o toque em
            # evento de mouse, comum em muitos ambientes)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_press(event.pos)
            elif event.type == pygame.MOUSEMOTION and self.dragging_tile is not None:
                self._handle_drag(event.pos)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self._handle_release(event.pos)

    def _handle_press(self, pos):
        g = self.game

        if g.game_over:
            if self.match_over:
                self._start_new_match()
            else:
                self._start_next_round()
            return

        if g.current != 0:
            return

        if self.BONEYARD_BTN.collidepoint(pos):
            if g.boneyard:
                drawn = g.draw_from_boneyard(0)
                self._flash("Comprou: " + str(drawn))
            else:
                self._flash("Estoque vazio!")
            return

        if self.PASS_BTN.collidepoint(pos):
            if not g.has_playable(0):
                g.pass_turn(0)
            else:
                self._flash("Você ainda pode jogar!")
            return

        # Início de um possível arraste a partir de uma pedra da mão
        tile = self._tile_at_hand(pos)
        if tile:
            rect = self._hand_rects[tile]
            self.dragging_tile = tile
            self.drag_pos = pos
            self.drag_offset = (pos[0] - rect.x, pos[1] - rect.y)
            self.drag_origin = pos
            self.drag_moved = False
            self.selected = tile
            return

        # Toque na mesa sem arrastar (mantém o fluxo antigo: tocar a pedra
        # selecionada e depois tocar a mesa também funciona)
        if self.selected:
            self._try_play_at(pos)

    def _handle_drag(self, pos):
        if self.dragging_tile is None:
            return
        self.drag_pos = pos
        dx = pos[0] - self.drag_origin[0]
        dy = pos[1] - self.drag_origin[1]
        if dx * dx + dy * dy > 36:  # limiar pequeno pra distinguir de um toque
            self.drag_moved = True

    def _handle_release(self, pos):
        if self.dragging_tile is None:
            return
        tile = self.dragging_tile
        self.dragging_tile = None

        if not self.drag_moved:
            # Foi só um toque na pedra (sem arrastar) → apenas seleciona
            return

        if self.BOARD_AREA.collidepoint(pos):
            self._try_play_at(pos)
        # Se soltar fora da mesa (ex: de volta na própria mão), cancela o
        # arraste e mantém a pedra selecionada na mão, sem jogar.

    def _try_play_at(self, pos):
        g = self.game
        if not self.selected:
            return
        side = self._board_side_clicked(pos)
        if side is None:
            self._flash("Solte a pedra sobre a mesa")
            return

        sides = g.playable_sides(self.selected)
        if side in sides:
            g.play(0, self.selected, side)
            self.selected = None
        else:
            # Não joga automaticamente no outro lado — o jogador escolhe
            # onde soltar, e se não encaixar ali, avisa em vez de corrigir.
            lado_pt = "esquerda" if side == "left" else "direita"
            self._flash(f"Não encaixa na {lado_pt}")

    # ── Desenho ────────────────────────────────────────────────────────────────
    def _draw(self):
        s = self.screen
        s.fill(C_BG)
        pygame.draw.rect(s, C_FELT, self.BOARD_AREA.inflate(-10, -10), border_radius=16)

        self._draw_top_bar()
        self._draw_opponent_hand()
        self._draw_board()
        self._draw_hand_area()
        self._draw_buttons()
        self._draw_dragging_tile()
        if self.game.game_over:
            self._draw_game_over()

    def _draw_dragging_tile(self):
        if self.dragging_tile is None or not self.drag_moved:
            return
        tile = self.dragging_tile
        x = self.drag_pos[0] - self.drag_offset[0]
        y = self.drag_pos[1] - self.drag_offset[1]

        over_board = self.BOARD_AREA.collidepoint(self.drag_pos)
        side = self._board_side_clicked(self.drag_pos) if over_board else None
        can_drop = side is not None and side in self.game.playable_sides(tile)

        draw_tile(self.screen, tile, x, y, selected=True, playable=can_drop, alpha=230)

    def _draw_top_bar(self):
        g = self.game
        stk = font_sm.render(f"Estoque: {len(g.boneyard)}", True, C_TEXT_DIM)
        self.screen.blit(stk, (10, 6))

        who = "Sua vez" if g.current == 0 else "Vez do PC..."
        col = C_PLAYER if g.current == 0 else C_OPPONENT
        ind = font_sm.render(who, True, col)
        self.screen.blit(ind, (SCREEN_W - ind.get_width() - 10, 6))

        # Placar da partida (regra: primeiro a 6 pontos vence) e nº da rodada
        placar = font_sm.render(
            f"Você {self.match_scores[0]} × {self.match_scores[1]} PC   "
            f"(rodada {self.round_num}, meta {self.MATCH_TARGET_POINTS} pts)",
            True, C_TEXT)
        self.screen.blit(placar, (SCREEN_W // 2 - placar.get_width() // 2, 6))

        if g.message:
            msg = font_sm.render(g.message, True, C_TURN_IND)
            self.screen.blit(msg, (SCREEN_W // 2 - msg.get_width() // 2, self.TOP_BAR_H - 16))

    def _draw_opponent_hand(self):
        hand = self.game.hands[1]
        n = len(hand)
        y = self.TOP_BAR_H + 4

        label = font_sm.render(f"Computador ({n})", True, C_OPPONENT)
        self.screen.blit(label, (SCREEN_W // 2 - label.get_width() // 2, y))
        y += 18

        # tamanho reduzido para caber a mão inteira em telas estreitas
        mini_w, mini_h = 22, 40
        gap = 3
        total_w = n * (mini_w + gap)
        sx = max(10, SCREEN_W // 2 - total_w // 2)

        fake = Tile(0, 0)
        for i in range(n):
            x = sx + i * (mini_w + gap)
            rect = pygame.Rect(x, y, mini_w, mini_h)
            pygame.draw.rect(self.screen, C_BONE, rect, border_radius=4)
            pygame.draw.rect(self.screen, C_BONE_DARK, rect, 1, border_radius=4)
            for gx in range(0, mini_w, 6):
                pygame.draw.line(self.screen, C_BONE_DARK, (x + gx, y), (x + gx, y + mini_h), 1)

    def _draw_board(self):
        g = self.game
        if not g.board:
            txt = font_sm.render("Arraste uma pedra até aqui para jogar", True, C_TEXT_DIM)
            self.screen.blit(txt, (SCREEN_W // 2 - txt.get_width() // 2, self.BOARD_AREA.centery))
            return

        positions = self._calc_board_positions()
        for i, (tile, (tx, ty)) in enumerate(zip(g.board, positions)):
            is_end = (i == 0 or i == len(g.board) - 1)
            draw_tile(self.screen, tile, tx, ty,
                      playable=is_end and self.selected is not None and
                               self.selected in [g.board[0] if i == 0 else g.board[-1]])

        if positions:
            lx, ly = positions[0]
            rx, ry = positions[-1]
            lt = g.board[0]; rt = g.board[-1]
            lw = TILE_H if lt.horizontal else TILE_W
            rw = TILE_H if rt.horizontal else TILE_W

            ltxt = font_sm.render(f"← {g.left_end}", True, C_TURN_IND)
            rtxt = font_sm.render(f"{g.right_end} →", True, C_TURN_IND)
            if len(g.board) == 1:
                # As duas pontas coincidem na mesma pedra: separa os
                # rótulos para os dois lados dela, não sobrepostos.
                self.screen.blit(ltxt, (lx - ltxt.get_width() - 6, ly + lw // 2 - ltxt.get_height() // 2))
                self.screen.blit(rtxt, (rx + (TILE_H if rt.horizontal else TILE_W) + 6, ry + lw // 2 - rtxt.get_height() // 2))
            else:
                self.screen.blit(ltxt, (lx + lw // 2 - ltxt.get_width() // 2, ly - 18))
                self.screen.blit(rtxt, (rx + rw // 2 - rtxt.get_width() // 2, ry - 18))

    def _calc_board_positions(self):
        g = self.game
        if not g.board:
            return []

        cx = SCREEN_W // 2
        cy = self.BOARD_AREA.centery

        HGAP, VGAP = 3, 3
        total_w = sum((TILE_H if t.horizontal else TILE_W) + HGAP for t in g.board)

        x = cx - total_w // 2
        y = cy - TILE_H // 2
        MAX_X = SCREEN_W - 40
        MIN_X = 20
        row_y = y
        positions = []

        for t in g.board:
            tw = TILE_H if t.horizontal else TILE_W
            th = TILE_W if t.horizontal else TILE_H
            if x + tw > MAX_X:
                x = cx - total_w // 2
                row_y += th + VGAP + 16
            if x < MIN_X:
                x = MIN_X
            positions.append((x, row_y - (th - TILE_H) // 2))
            x += tw + HGAP

        return positions

    def _draw_hand_area(self):
        g = self.game
        hand = g.hands[0]
        n = len(hand)

        pygame.draw.rect(self.screen, C_SCORE_BG, self.HAND_AREA.inflate(-4, -4), border_radius=10)

        label = font_sm.render(
            "Sua mão" + (" — SUA VEZ" if g.current == 0 and not g.game_over else ""),
            True, C_PLAYER if g.current == 0 else C_TEXT_DIM)
        self.screen.blit(label, (12, self.HAND_AREA.y + 6))

        self._hand_rects = {}
        if not hand:
            return

        sy = self.HAND_AREA.y + self.HAND_LABEL_H + 6
        avail_w = SCREEN_W - 20
        # espaçamento normal, mas com sobreposição se não couber tudo
        step = TILE_W + 6
        if n > 1 and step * n > avail_w:
            step = max(20, (avail_w - TILE_W) // (n - 1))
        total_w = TILE_W + step * (n - 1) if n > 0 else 0
        sx = max(10, (SCREEN_W - total_w) // 2)

        # desenha em ordem normal; guarda retângulos para detecção em ordem
        # inversa (pedra mais à direita fica "por cima" em caso de sobreposição)
        for i, tile in enumerate(hand):
            x = sx + i * step
            y = sy
            self._hand_rects[tile] = tile_rect(tile, x, sy)

            if tile is self.dragging_tile and self.drag_moved:
                # está sendo arrastada: não desenha na posição da mão,
                # será desenhada por cima de tudo em _draw()
                continue

            sides = g.playable_sides(tile) if g.current == 0 else []
            is_sel = (tile == self.selected)
            if is_sel:
                y -= 10
            draw_tile(self.screen, tile, x, y,
                      selected=is_sel,
                      playable=bool(sides) and g.current == 0)

    def _draw_buttons(self):
        g = self.game

        for rect, label, enabled in [
            (self.BONEYARD_BTN, f"Comprar ({len(g.boneyard)})", bool(g.boneyard) and g.current == 0),
            (self.PASS_BTN,     "Passar vez",                   g.current == 0),
        ]:
            col = C_BTN if enabled else C_BTN_DIS
            pygame.draw.rect(self.screen, col, rect, border_radius=10)
            pygame.draw.rect(self.screen, C_BONE_DARK, rect, 1, border_radius=10)
            txt = font_md.render(label, True, C_BTN_TXT if enabled else C_TEXT_DIM)
            self.screen.blit(txt, (rect.centerx - txt.get_width() // 2,
                                    rect.centery - txt.get_height() // 2))

    def _draw_game_over(self):
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        self.screen.blit(overlay, (0, 0))

        box = pygame.Rect(SCREEN_W // 2 - 160, SCREEN_H // 2 - 100, 320, 200)
        pygame.draw.rect(self.screen, C_SCORE_BG, box, border_radius=16)
        pygame.draw.rect(self.screen, C_TURN_IND, box, 3, border_radius=16)

        title = font_xl.render("Fim de Jogo", True, C_TURN_IND)
        msg   = font_md.render(self.game.message, True, C_TEXT)
        hint  = font_sm.render("Toque em qualquer lugar para jogar novamente", True, C_TEXT_DIM)

        self.screen.blit(title, (box.centerx - title.get_width() // 2, box.y + 20))
        self.screen.blit(msg,   (box.centerx - msg.get_width() // 2,   box.y + 70))
        self.screen.blit(hint,  (box.centerx - hint.get_width() // 2,  box.y + 150))

    # ── Helpers ────────────────────────────────────────────────────────────────
    def _tile_at_hand(self, pos) -> Optional[Tile]:
        # percorre em ordem inversa: pedra desenhada por último (mais à
        # direita, sobreposta) tem prioridade no toque
        for tile, rect in reversed(list(self._hand_rects.items())):
            expanded = rect.inflate(TOUCH_PAD, TOUCH_PAD * 2)
            if expanded.collidepoint(pos):
                return tile
        return None

    def _board_side_clicked(self, pos) -> Optional[str]:
        g = self.game
        if not g.board:
            return "left"
        positions = self._calc_board_positions()
        if not positions:
            return None

        lx, ly = positions[0]
        lt = g.board[0]
        lw = TILE_H if lt.horizontal else TILE_W
        lh = TILE_W if lt.horizontal else TILE_H

        rx, ry = positions[-1]
        rt = g.board[-1]
        rw = TILE_H if rt.horizontal else TILE_W
        rh = TILE_W if rt.horizontal else TILE_H

        # Caso especial: só existe UMA pedra na mesa (a primeira jogada).
        # As pontas esquerda e direita coincidem na mesma posição física,
        # então os retângulos abaixo se sobreporiam e a checagem da
        # esquerda "ganharia" sempre. Aqui decidimos pelo lado em que o
        # toque caiu em relação ao centro dessa pedra: solta à esquerda
        # do centro → "left"; à direita do centro → "right".
        if len(g.board) == 1:
            if not self.BOARD_AREA.collidepoint(pos):
                return None
            tile_cx = lx + lw / 2
            return "left" if pos[0] < tile_cx else "right"

        if pygame.Rect(lx - TOUCH_PAD * 2, ly, lw + TOUCH_PAD * 2, lh).collidepoint(pos):
            return "left"

        if pygame.Rect(rx, ry, rw + TOUCH_PAD * 2, rh).collidepoint(pos):
            return "right"

        # Solto em algum ponto do meio da mesa → decide pelo lado
        # geometricamente mais próximo de onde a pedra foi largada.
        # Importante: aqui NÃO olhamos quais lados são jogáveis — o
        # jogador escolhe o lado pela posição, não o jogo por conveniência.
        if self.BOARD_AREA.collidepoint(pos):
            lcx, lcy = lx + lw / 2, ly + lh / 2
            rcx, rcy = rx + rw / 2, ry + rh / 2
            dist_left  = (pos[0] - lcx) ** 2 + (pos[1] - lcy) ** 2
            dist_right = (pos[0] - rcx) ** 2 + (pos[1] - rcy) ** 2
            return "left" if dist_left <= dist_right else "right"
        return None

    def _flash(self, msg: str):
        self.game.message = msg
        self.msg_timer = 2000

        def clear():
            time.sleep(2)
            if self.game.message == msg:
                self.game.message = ""
        threading.Thread(target=clear, daemon=True).start()

    def _reset_drag_state(self):
        self.dragging_tile = None
        self.drag_moved = False
        self.selected = None

    def _start_new_match(self):
        """Zera o placar e começa uma partida nova do zero."""
        self.match_scores = [0, 0]
        self.match_over = False
        self.match_winner = -1
        self.round_num = 1
        self.round_scored = False
        self.next_starter = None
        self.game = DominoGame()
        self._reset_drag_state()

    def _start_next_round(self):
        """Mantém o placar da partida e começa a próxima rodada. Regra:
        a rodada seguinte começa com o outro jogador (sentido anti-horário,
        que com 2 jogadores é simplesmente alternar)."""
        self.round_num += 1
        self.round_scored = False
        self.game = DominoGame(forced_starter=self.next_starter)
        self._reset_drag_state()


# ── Entrypoint ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    ui = UI()
    ui.run()
