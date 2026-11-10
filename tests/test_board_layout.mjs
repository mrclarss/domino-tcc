import assert from "node:assert/strict";
import { createRequire } from "node:module";
import test from "node:test";

const require = createRequire(import.meta.url);
const { layoutChain } = require("../liga/static/js/board-layout.js");

function overlaps(a, b, w, h) {
  const ox = Math.min(a.x + w, b.x + w) - Math.max(a.x, b.x);
  const oy = Math.min(a.y + h, b.y + h) - Math.max(a.y, b.y);
  return ox > 0 && oy > 0;
}

function touches(a, b, w, h, gap) {
  const horizGap = Math.max(b.x - (a.x + w), a.x - (b.x + w));
  const vertGap = Math.max(b.y - (a.y + h), a.y - (b.y + h));
  const overlapX = Math.min(a.x + w, b.x + w) - Math.max(a.x, b.x);
  const overlapY = Math.min(a.y + h, b.y + h) - Math.max(a.y, b.y);
  const sideBySide = Math.abs(horizGap - gap) < 0.01 && overlapY > 0;
  const stacked = Math.abs(vertGap - gap) < 0.01 && overlapX > 0;
  return sideBySide || stacked;
}

test("mesa vazia não ocupa espaço", () => {
  const layout = layoutChain(0, 400, 150, 96, 12);
  assert.deepEqual(layout.tiles, []);
  assert.equal(layout.width, 0);
  assert.equal(layout.height, 0);
});

test("não dobra antes de encostar na borda", () => {
  const tileW = 100;
  const gap = 10;
  const maxWidth = 3 * tileW + 2 * gap;
  const layout = layoutChain(3, maxWidth, tileW, 70, gap);
  assert.equal(layout.cols, 3);
  assert.equal(layout.rows, 1);
  for (const spot of layout.tiles) assert.equal(spot.y, 0);
  assert.deepEqual(layout.tiles.map((spot) => spot.x), [0, 110, 220]);
});

test("a peça seguinte dobra na borda direita e a volta anda para a esquerda", () => {
  const tileW = 150;
  const tileH = 96;
  const gap = 12;
  const maxWidth = 360;
  const layout = layoutChain(8, maxWidth, tileW, tileH, gap);
  assert.ok(layout.cols >= 2);
  assert.ok(layout.width <= maxWidth);
  assert.equal(layout.tiles[0].x, 0);
  assert.equal(layout.tiles[0].y, 0);
  const edge = layout.tiles[layout.cols - 1];
  assert.equal(edge.y, 0);
  assert.equal(edge.x + tileW, layout.width);
  const turned = layout.tiles[layout.cols];
  assert.equal(turned.x, edge.x);
  assert.equal(turned.y, tileH + gap);
  const back = layout.tiles[layout.cols + 1];
  assert.ok(back.x < turned.x);
  assert.equal(back.y, turned.y);
});

test("a terceira fileira volta a andar para a direita, fechando o retângulo", () => {
  const layout = layoutChain(7, 320, 100, 60, 8);
  assert.equal(layout.cols, 3);
  assert.deepEqual(
    layout.tiles.map((spot) => [spot.col, spot.row]),
    [
      [0, 0], [1, 0], [2, 0],
      [2, 1], [1, 1], [0, 1],
      [0, 2],
    ],
  );
});

test("peças consecutivas se encostam e nenhuma se sobrepõe", () => {
  const tileW = 150;
  const tileH = 96;
  const gap = 12;
  const layout = layoutChain(17, 520, tileW, tileH, gap);
  for (let i = 0; i < layout.tiles.length; i++) {
    for (let j = i + 1; j < layout.tiles.length; j++) {
      assert.equal(overlaps(layout.tiles[i], layout.tiles[j], tileW, tileH), false);
    }
    if (i > 0) {
      assert.equal(touches(layout.tiles[i - 1], layout.tiles[i], tileW, tileH, gap), true);
    }
    const spot = layout.tiles[i];
    assert.ok(spot.x >= 0 && spot.y >= 0);
    assert.ok(spot.x + tileW <= layout.width + 0.01);
    assert.ok(spot.y + tileH <= layout.height + 0.01);
  }
  assert.ok(layout.height > tileH);
  assert.ok(layout.width > tileW);
});

test("uma corrente curta não reserva colunas vazias", () => {
  const tileW = 150;
  const gap = 12;
  const layout = layoutChain(2, 800, tileW, 96, gap);
  assert.ok(layout.cols > 2);
  assert.equal(layout.width, tileW * 2 + gap);
  assert.equal(layout.height, 96);
  assert.equal(layout.tiles[1].x + tileW, layout.width);
});

test("uma peça mais larga que a mesa ainda cabe numa coluna", () => {
  const layout = layoutChain(3, 80, 150, 96, 10);
  assert.equal(layout.cols, 1);
  assert.deepEqual(layout.tiles.map((spot) => spot.x), [0, 0, 0]);
  assert.ok(layout.tiles[1].y > layout.tiles[0].y);
});
