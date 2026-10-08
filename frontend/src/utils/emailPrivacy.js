// CSP is applied before sender markup; it also covers srcset, CSS URLs and SVG images.
export function emailCsp(loadExternalImages = false) {
  return `default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; img-src data: cid:${loadExternalImages ? ' https: http:' : ''}; font-src data:; media-src 'none'; frame-src 'none'; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'`;
}
// Parse in an inert template: preserve tables/inline styles, remove navigation/active markup.
export function cleanEmailMarkup(body, doc = document) {
  const template = doc.createElement('template');
  template.innerHTML = body;
  template.content.querySelectorAll('script,iframe,object,embed,base,meta,link,form').forEach(el => el.remove());
  template.content.querySelectorAll('*').forEach(el => {
    for (const attr of [...el.attributes]) {
      if (/^on/i.test(attr.name) || ['srcdoc','ping'].includes(attr.name)) el.removeAttribute(attr.name);
    }
    if (el.tagName === 'A') {
      const href = el.getAttribute('href') || '';
      if (!/^(https?:|mailto:|#)/i.test(href.trim())) el.removeAttribute('href');
      el.setAttribute('target', '_blank'); el.setAttribute('rel', 'noopener noreferrer');
    }
  });
  return template.innerHTML;
}
