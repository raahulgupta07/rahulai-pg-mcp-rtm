/* Minimal, safe Markdown → HTML renderer.
   Supports: headings, bold, italic, inline code, code fences, tables,
   ordered/unordered lists, blockquotes, horizontal rules, links, paragraphs.
   Input is HTML-escaped first, so rendered content cannot inject markup. */

function esc(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function inline(s: string): string {
  return s
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>')
    .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
}

export function renderMarkdown(md: string): string {
  if (!md) return '';
  const lines = esc(md).replace(/\r\n/g, '\n').split('\n');
  const out: string[] = [];
  let i = 0;
  let para: string[] = [];

  const flushPara = () => {
    if (para.length) {
      out.push(`<p>${inline(para.join(' '))}</p>`);
      para = [];
    }
  };

  while (i < lines.length) {
    const line = lines[i];

    // Code fence
    if (/^```/.test(line.trim())) {
      flushPara();
      const code: string[] = [];
      i++;
      while (i < lines.length && !/^```/.test(lines[i].trim())) {
        code.push(lines[i]);
        i++;
      }
      i++; // skip closing fence
      out.push(`<pre><code>${code.join('\n')}</code></pre>`);
      continue;
    }

    // Horizontal rule
    if (/^(-{3,}|\*{3,}|_{3,})\s*$/.test(line.trim())) {
      flushPara();
      out.push('<hr />');
      i++;
      continue;
    }

    // Heading
    const h = line.match(/^(#{1,6})\s+(.*)$/);
    if (h) {
      flushPara();
      const lvl = h[1].length;
      out.push(`<h${lvl}>${inline(h[2].trim())}</h${lvl}>`);
      i++;
      continue;
    }

    // Table
    if (/^\s*\|.*\|\s*$/.test(line) &&
        i + 1 < lines.length &&
        /^\s*\|?[\s:|-]+\|?\s*$/.test(lines[i + 1]) &&
        lines[i + 1].includes('-')) {
      flushPara();
      const splitRow = (r: string) =>
        r.trim().replace(/^\||\|$/g, '').split('|').map(c => c.trim());
      const header = splitRow(line);
      i += 2; // skip header + separator
      const body: string[][] = [];
      while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) {
        body.push(splitRow(lines[i]));
        i++;
      }
      let t = '<table><thead><tr>';
      t += header.map(c => `<th>${inline(c)}</th>`).join('');
      t += '</tr></thead><tbody>';
      for (const row of body) {
        t += '<tr>' + header.map((_, idx) => `<td>${inline(row[idx] ?? '')}</td>`).join('') + '</tr>';
      }
      t += '</tbody></table>';
      out.push(t);
      continue;
    }

    // Blockquote — note: input is already HTML-escaped, so '>' is now '&gt;'
    if (/^\s*&gt;\s?/.test(line)) {
      flushPara();
      const quote: string[] = [];
      while (i < lines.length && /^\s*&gt;\s?/.test(lines[i])) {
        quote.push(lines[i].replace(/^\s*&gt;\s?/, ''));
        i++;
      }
      out.push(`<blockquote>${inline(quote.join(' '))}</blockquote>`);
      continue;
    }

    // Unordered list
    if (/^\s*[-*+]\s+/.test(line)) {
      flushPara();
      const items: string[] = [];
      while (i < lines.length && /^\s*[-*+]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*[-*+]\s+/, ''));
        i++;
      }
      out.push('<ul>' + items.map(it => `<li>${inline(it)}</li>`).join('') + '</ul>');
      continue;
    }

    // Ordered list
    if (/^\s*\d+\.\s+/.test(line)) {
      flushPara();
      const items: string[] = [];
      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*\d+\.\s+/, ''));
        i++;
      }
      out.push('<ol>' + items.map(it => `<li>${inline(it)}</li>`).join('') + '</ol>');
      continue;
    }

    // Blank line — paragraph break
    if (line.trim() === '') {
      flushPara();
      i++;
      continue;
    }

    // Paragraph text
    para.push(line.trim());
    i++;
  }
  flushPara();
  return out.join('\n');
}
