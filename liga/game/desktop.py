"""Cliente pygame do Liga!. A mesa usa o mesmo motor do site.

Rode na pasta do projeto:

    python -m liga.game.desktop
"""

from __future__ import annotations

import pygame

from liga.game.ai import run_ai_turn
from liga.game.chemistry import FUNCTIONS
from liga.game.engine import draw, label as face_label, legal_moves, new_state, pass_turn, play

WIDTH, HEIGHT = 1100, 720
BG = (236, 243, 244)
TEAL = (1, 162, 154)
PURPLE = (142, 92, 255)
INK = (76, 25, 147)
CREAM = (247, 244, 238)
LINE = (201, 192, 178)
MUTED = (128, 149, 160)


def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Liga! — dominó da química orgânica")
    clock = pygame.time.Clock()
    fonts = {
        "big": pygame.font.SysFont("segoeui", 42, bold=True),
        "ui": pygame.font.SysFont("segoeui", 20),
        "small": pygame.font.SysFont("segoeui", 14),
        "tile": pygame.font.SysFont("segoeui", 13, bold=True),
    }
    while True:
        difficulty = _menu(screen, clock, fonts)
        if difficulty is None:
            break
        if _match(screen, clock, fonts, difficulty) is None:
            break
    pygame.quit()


def _menu(screen, clock, fonts):
    options = [("facil", "FÁCIL"), ("medio", "MÉDIO"), ("dificil", "DIFÍCIL")]
    while True:
        screen.fill(BG)
        title = fonts["big"].render("Liga!", True, INK)
        screen.blit(title, title.get_rect(center=(WIDTH // 2, 160)))
        subtitle = fonts["ui"].render("Conecte e Aprenda.", True, TEAL)
        screen.blit(subtitle, subtitle.get_rect(center=(WIDTH // 2, 210)))
        hint = fonts["small"].render("Escolha a dificuldade da IA. Esc fecha.", True, MUTED)
        screen.blit(hint, hint.get_rect(center=(WIDTH // 2, 250)))
        rects = []
        for index, (key, label) in enumerate(options):
            rect = pygame.Rect(0, 0, 220, 64)
            rect.center = (WIDTH // 2, 340 + index * 84)
            color = TEAL if index == 0 else PURPLE if index == 1 else (145, 185, 202)
            pygame.draw.rect(screen, color, rect, border_radius=12)
            text = fonts["ui"].render(label, True, (255, 255, 255))
            screen.blit(text, text.get_rect(center=rect.center))
            rects.append((rect, key))
        pygame.display.flip()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return None
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for rect, key in rects:
                    if rect.collidepoint(event.pos):
                        return key
        clock.tick(30)


def _match(screen, clock, fonts, difficulty: str):
    state = new_state(7)
    selected = None
    message = "Ligue funções iguais. D compra, P passa, Esc volta."
    while True:
        if state["status"] == "playing" and state["turn"] == 2:
            run_ai_turn(state, difficulty, 2)
            message = _line(state)
        hits = []
        screen.fill(BG)
        _header(screen, fonts, state, message)
        _board(screen, fonts, state, selected, hits)
        _hand(screen, fonts, state, selected, hits)
        _buttons(screen, fonts, state, hits)
        if state["status"] == "finished":
            _overlay(screen, fonts, state)
        pygame.display.flip()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return "menu"
            if state["status"] != "playing" or state["turn"] != 1:
                if event.type == pygame.MOUSEBUTTONDOWN and state["status"] == "finished":
                    return "menu"
                continue
            if event.type == pygame.KEYDOWN and event.key == pygame.K_d:
                ok, error = draw(state, 1)
                message = error or _line(state)
                selected = None
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_p:
                ok, error = pass_turn(state, 1)
                message = error or _line(state)
                selected = None
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                selected, message = _click(state, selected, hits, event.pos, message)
        clock.tick(30)


def _click(state, selected, hits, pos, message):
    for rect, kind, payload in hits:
        if not rect.collidepoint(pos):
            continue
        if kind == "tile":
            sides = payload["sides"]
            if not sides:
                return selected, "Essa peça não encaixa agora."
            if len(sides) == 1:
                _ok, error = play(state, 1, payload["tile_id"], sides[0])
                return None, error or _line(state)
            return payload["tile_id"], "Escolha a ponta esquerda ou a direita da mesa."
        if kind == "side" and selected is not None:
            ok, error = play(state, 1, selected, payload)
            return None, error or _line(state)
        if kind == "draw":
            ok, error = draw(state, 1)
            return None, error or _line(state)
        if kind == "pass":
            ok, error = pass_turn(state, 1)
            return None, error or _line(state)
    return selected, message


def _header(screen, fonts, state, message) -> None:
    pygame.draw.rect(screen, TEAL, (0, 0, WIDTH, 92))
    you = fonts["ui"].render(f"Você  {state['scores']['1']} pts  ·  {len(state['hands']['1'])} peças", True, (13, 103, 99))
    ia = fonts["ui"].render(f"Liga IA  {state['scores']['2']} pts  ·  {len(state['hands']['2'])} peças", True, INK)
    pygame.draw.rect(screen, (194, 255, 242), (24, 22, 320, 52), border_radius=10)
    pygame.draw.rect(screen, (221, 206, 254), (WIDTH - 344, 22, 320, 52), border_radius=10)
    screen.blit(you, (40, 36))
    screen.blit(ia, (WIDTH - 328, 36))
    note = fonts["small"].render(message, True, (28, 43, 48))
    screen.blit(note, (24, 104))
    bone = fonts["small"].render(f"Cemitério: {len(state['boneyard'])}", True, TEAL)
    screen.blit(bone, (WIDTH - 180, 104))


def _board(screen, fonts, state, selected, hits) -> None:
    area = pygame.Rect(24, 140, WIDTH - 48, 250)
    pygame.draw.rect(screen, (255, 255, 255), area, border_radius=16)
    moves = {item["tile_id"]: item["sides"] for item in legal_moves(state, 1)}
    sides = moves.get(selected, []) if selected is not None else []
    if not state["board"]:
        text = fonts["ui"].render("A mesa está vazia.", True, MUTED)
        screen.blit(text, text.get_rect(center=area.center))
        return
    tile_w, tile_h = 116, 64
    total = len(state["board"]) * (tile_w + 8)
    x = max(area.left + 16, area.centerx - total // 2)
    y = area.centery - tile_h // 2
    if "left" in sides:
        spot = pygame.Rect(x - 58, y, 48, tile_h)
        pygame.draw.rect(screen, (194, 255, 242), spot, border_radius=8)
        hits.append((spot, "side", "left"))
    for placed in state["board"]:
        rect = pygame.Rect(x, y, tile_w, tile_h)
        _tile(screen, fonts["tile"], rect, placed["left"], placed["right"], True)
        x += tile_w + 8
    if "right" in sides:
        spot = pygame.Rect(x, y, 48, tile_h)
        pygame.draw.rect(screen, (194, 255, 242), spot, border_radius=8)
        hits.append((spot, "side", "right"))


def _hand(screen, fonts, state, selected, hits) -> None:
    label = fonts["small"].render("SUA MÃO", True, TEAL)
    screen.blit(label, (24, 408))
    moves = {item["tile_id"]: item["sides"] for item in legal_moves(state, 1)} if state["turn"] == 1 else {}
    x = 24
    for tile_id in state["hands"]["1"]:
        tile = state["tiles"][tile_id]
        rect = pygame.Rect(x, 440, 78, 132)
        _tile(screen, fonts["tile"], rect, tile["a"], tile["b"], False)
        if tile_id == selected:
            pygame.draw.rect(screen, PURPLE, rect, 3, border_radius=10)
        elif tile_id in moves:
            pygame.draw.rect(screen, TEAL, rect, 2, border_radius=10)
        if state["turn"] == 1 and state["status"] == "playing":
            hits.append((rect, "tile", {"tile_id": tile_id, "sides": moves.get(tile_id, [])}))
        x += 88


def _buttons(screen, fonts, state, hits) -> None:
    draw_rect = pygame.Rect(24, 600, 220, 56)
    pass_rect = pygame.Rect(260, 600, 220, 56)
    pygame.draw.rect(screen, (194, 255, 242), draw_rect, border_radius=10)
    pygame.draw.rect(screen, (255, 255, 255), pass_rect, border_radius=10)
    pygame.draw.rect(screen, MUTED, pass_rect, 1, border_radius=10)
    screen.blit(fonts["ui"].render("COMPRAR", True, TEAL), (78, 616))
    screen.blit(fonts["ui"].render("PASSAR", True, MUTED), (320, 616))
    if state["turn"] == 1 and state["status"] == "playing":
        hits.append((draw_rect, "draw", None))
        hits.append((pass_rect, "pass", None))


def _overlay(screen, fonts, state) -> None:
    shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    shade.fill((16, 34, 38, 140))
    screen.blit(shade, (0, 0))
    end = state["end"]
    if end["winner"] == 1:
        text = "Você ganhou"
    elif end["winner"] == 2:
        text = "A IA ganhou"
    else:
        text = "Empate"
    box = pygame.Rect(0, 0, 460, 180)
    box.center = (WIDTH // 2, HEIGHT // 2)
    pygame.draw.rect(screen, BG, box, border_radius=16)
    title = fonts["big"].render(text, True, PURPLE)
    screen.blit(title, title.get_rect(center=(box.centerx, box.centery - 24)))
    detail = fonts["ui"].render("Clique para voltar ao menu", True, MUTED)
    screen.blit(detail, detail.get_rect(center=(box.centerx, box.centery + 28)))


def _tile(screen, font, rect, left, right, horizontal: bool) -> None:
    pygame.draw.rect(screen, CREAM, rect, border_radius=10)
    pygame.draw.rect(screen, LINE, rect, 1, border_radius=10)
    if horizontal:
        pygame.draw.line(screen, LINE, (rect.centerx, rect.top + 8), (rect.centerx, rect.bottom - 8))
        areas = (
            pygame.Rect(rect.left, rect.top, rect.w // 2, rect.h),
            pygame.Rect(rect.centerx, rect.top, rect.w // 2, rect.h),
        )
    else:
        pygame.draw.line(screen, LINE, (rect.left + 8, rect.centery), (rect.right - 8, rect.centery))
        areas = (
            pygame.Rect(rect.left, rect.top, rect.w, rect.h // 2),
            pygame.Rect(rect.left, rect.centery, rect.w, rect.h // 2),
        )
    for area, value in zip(areas, (left, right)):
        label = font.render(face_label(value), True, (36, 48, 56))
        screen.blit(label, label.get_rect(center=area.center))


def _line(state) -> str:
    last = state.get("last")
    if not last:
        return "Sua vez."
    name = last.get("name") or ""
    if last["verb"] == "play":
        who = "Você" if last["actor"] == 1 else "A IA"
        return f"{who} ligou na ponta {name}."
    if last["verb"] == "open":
        who = "Você" if last["actor"] == 1 else "A IA"
        return f"{who} abriu a mesa com {name}."
    if last["verb"] == "open-double":
        who = "Você" if last["actor"] == 1 else "A IA"
        return f"{who} abriu com a dupla de {name}."
    if last["verb"] == "draw":
        return "Peça comprada."
    if last["verb"] == "pass":
        return "Vez passada."
    return "Sua vez."


if __name__ == "__main__":
    main()
