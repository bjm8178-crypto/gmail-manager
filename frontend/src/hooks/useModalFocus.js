import { useEffect, useRef } from 'react';
export function useModalFocus(onClose) {
  const ref = useRef(null);
  const closeRef = useRef(onClose); closeRef.current = onClose;
  useEffect(() => {
    const dialog = ref.current, previous = document.activeElement;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const focusables = () => [...dialog.querySelectorAll('button:not(:disabled),a[href],input:not(:disabled),select:not(:disabled),textarea:not(:disabled),iframe,[tabindex="0"]')].filter(el => el.getClientRects().length);
    (focusables()[0] || dialog).focus();
    const key = e => {
      if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); closeRef.current(); }
      if (e.key === 'Tab') {
        const items = focusables(), first = items[0], last = items.at(-1);
        if (!first) { e.preventDefault(); dialog.focus(); }
        else if (e.shiftKey && (document.activeElement === first || document.activeElement === dialog)) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    };
    const focus = e => { if (!dialog.contains(e.target)) (focusables()[0] || dialog).focus(); };
    document.addEventListener('keydown', key);
    document.addEventListener('focusin', focus);
    return () => {
      document.removeEventListener('keydown', key); document.removeEventListener('focusin', focus);
      document.body.style.overflow = overflow;
      if (previous?.isConnected) previous.focus();
    };
  }, []);
  return ref;
}
