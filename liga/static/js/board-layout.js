/* Caminho da mesa: a corrente segue em linha até a borda e dobra,
   formando um retângulo (ida e volta), como dominó na mesa. */
(function (factory) {
  var api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof window !== "undefined") window.LigaBoard = api;
})(function () {
  function layoutChain(count, maxWidth, tileW, tileH, gap) {
    var safeGap = Math.max(0, Number(gap) || 0);
    var w = Math.max(1, Number(tileW) || 1);
    var h = Math.max(1, Number(tileH) || 1);
    var limit = Math.max(0, Number(maxWidth) || 0);
    if (count <= 0) return { cols: 0, rows: 0, width: 0, height: 0, tiles: [] };
    var strideX = w + safeGap;
    var strideY = h + safeGap;
    var cols = Math.max(1, Math.floor((limit + safeGap) / strideX) || 1);
    var rows = Math.ceil(count / cols);
    var tiles = [];
    var width = 0;
    var height = 0;
    for (var i = 0; i < count; i++) {
      var row = Math.floor(i / cols);
      var col = i % cols;
      if (row % 2 === 1) col = cols - 1 - col;
      var x = col * strideX;
      var y = row * strideY;
      tiles.push({ i: i, row: row, col: col, x: x, y: y });
      width = Math.max(width, x + w);
      height = Math.max(height, y + h);
    }
    return { cols: cols, rows: rows, width: width, height: height, tiles: tiles };
  }

  return { layoutChain: layoutChain };
});
