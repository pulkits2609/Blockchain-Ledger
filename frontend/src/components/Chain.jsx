import { useLayoutEffect, useRef, useState } from 'react';
import { blockTitle, dateText, shortHash } from '../ledgerHelpers.js';
import BlockDetails from './BlockDetails.jsx';
import { snapshotStatus, statusLabel } from '../snapshotStatus.js';

export default function Chain({ ledgerId, blocks, selectedIndex, onSelect, canDownload, report }) {
  const container = useRef(null);
  const cards = useRef(new Map());
  const [columns, setColumns] = useState(3);
  const [paths, setPaths] = useState([]);

  useLayoutEffect(() => {
    const element = container.current;
    function measure() {
      const bounds = element.getBoundingClientRect();
      setColumns(bounds.width < 580 ? 1 : bounds.width < 900 ? 2 : 3);
      const links = [];
      for (let index = 1; index < blocks.length; index += 1) {
        const previous = cards.current.get(index - 1)?.getBoundingClientRect();
        const current = cards.current.get(index)?.getBoundingClientRect();
        if (!previous || !current) continue;
        const startX = previous.right - bounds.left + 12;
        const startY = previous.top - bounds.top + previous.height / 2;
        const endX = current.left - bounds.left;
        const endY = current.top - bounds.top + current.height / 2;
        if (Math.abs(startY - endY) < 2) {
          links.push(`M ${startX} ${startY} H ${endX - 5}`);
        } else {
          // The row-return link uses the gutter, never the open detail panel.
          const turnY = previous.bottom - bounds.top + 32;
          links.push(`M ${startX} ${startY} H ${bounds.width - 3} V ${turnY} H 3 V ${endY} H ${endX - 5}`);
        }
      }
      setPaths(links);
    }
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    cards.current.forEach(card => observer.observe(card));
    measure();
    return () => observer.disconnect();
  }, [blocks.length, columns, selectedIndex]);

  const rows = [];
  for (let start = 0; start < blocks.length; start += columns) rows.push(blocks.slice(start, start + columns));

  return <section className="chain" ref={container} aria-label="Live linked blocks" style={{ '--columns': columns }}>
    <svg className="chain-links" aria-hidden="true"><defs><marker id="link-arrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0 0 L7 3.5 L0 7"/></marker></defs>{paths.map((path, index) => <path className="chain-link" key={index} d={path} markerEnd="url(#link-arrow)"/>)}</svg>
    {rows.map((row, rowIndex) => {
      const selected = row.find(block => block.index === selectedIndex);
      return <div className="chain-row" key={rowIndex}>
        {row.map((block, column) => <button type="button" ref={element => {
          const position = rowIndex * columns + column;
          if (element) cards.current.set(position, element);
          else cards.current.delete(position);
        }} className={`block-card ${selectedIndex === block.index ? 'selected' : ''} ${block.index === 0 ? 'genesis' : ''} ${snapshotStatus(report, block.index)?.status || ''}`} key={`${rowIndex}-${column}`} onClick={() => onSelect(block.index)} aria-expanded={selectedIndex === block.index} aria-controls={selectedIndex === block.index ? `details-${block.index}` : undefined}>
          <span className="block-topline"><span>{block.index === 0 ? 'GENESIS' : 'RECORD'}</span><span>#{String(block.index).padStart(3, '0')}</span></span>
          <strong>{blockTitle(block)}</strong><code>{shortHash(block.hash)}</code>
          {snapshotStatus(report, block.index) && <span className="card-verdict">{statusLabel(snapshotStatus(report, block.index).status)}</span>}
          <span className="block-bottomline"><span>{block.index === 0 ? 'The starting block' : dateText(block.timestamp_ms)}</span><span aria-hidden="true">{selectedIndex === block.index ? '−' : '+'}</span></span>
        </button>)}
        {selected && <BlockDetails key={selected.index} ledgerId={ledgerId} block={selected} canDownload={canDownload} report={report}/>}
      </div>;
    })}
  </section>;
}
