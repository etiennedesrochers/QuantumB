/** Data table built from plain objects; values are set via textContent. */

import { el } from "../dom.js";

export function dataTable({ columns, rows, onRowClick, isActive, empty = "Nothing to show." }) {
  if (!rows || rows.length === 0) return el("p", { class: "muted", text: empty });

  const head = el("tr", {}, columns.map((col) => el("th", { text: col.label })));
  const body = rows.map((row, index) => {
    const tr = el("tr", {
      class: [
        onRowClick ? "clickable" : "",
        isActive?.(row) ? "is-active" : "",
      ].filter(Boolean).join(" "),
      onClick: onRowClick ? () => onRowClick(row) : undefined,
    }, columns.map((col) => {
      const value = col.render ? col.render(row, index) : row[col.key];
      return el("td", { class: col.class }, [value instanceof Node ? value : String(value ?? "")]);
    }));
    return tr;
  });

  return el("table", { class: "table" }, [
    el("thead", {}, [head]),
    el("tbody", {}, body),
  ]);
}
