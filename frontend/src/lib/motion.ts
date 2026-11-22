import { useEffect, useRef, useState } from 'react'

export const calm = () => matchMedia('(prefers-reduced-motion: reduce)').matches

/** One listener for every button. The ripple starts where the finger lands. */
export function installRipples() {
  document.addEventListener('pointerdown', (event) => {
    const button = (event.target as Element).closest<HTMLElement>('.btn:not(:disabled)')
    if (!button || calm()) return
    const box = button.getBoundingClientRect()
    const size = 2 * Math.hypot(Math.max(event.clientX - box.left, box.right - event.clientX), Math.max(event.clientY - box.top, box.bottom - event.clientY))
    const ripple = document.createElement('span')
    ripple.className = 'ripple'
    ripple.style.cssText = `width:${size}px;height:${size}px;left:${event.clientX - box.left - size / 2}px;top:${event.clientY - box.top - size / 2}px`
    button.append(ripple)
    ripple.animate(
      [{ transform: 'scale(0.1)', opacity: 0.28 }, { transform: 'scale(1)', opacity: 0 }],
      { duration: 620, easing: 'cubic-bezier(0.16, 1, 0.3, 1)' },
    ).onfinish = () => ripple.remove()
  }, { passive: true })
}

/** Let the boot screen finish its story once per visit, then lift it. Any key or tap skips it. */
export function finishBoot() {
  const boot = document.getElementById('boot')
  if (!boot || boot.dataset.leaving) return
  boot.dataset.leaving = 'true'
  const quick = document.documentElement.dataset.boot === 'quick' || calm()
  const leave = () => {
    if (boot.classList.contains('done')) return
    boot.classList.add('done')
    const remove = () => boot.remove()
    boot.addEventListener('animationend', (e) => e.target === boot && remove())
    setTimeout(remove, 900)
    try { sessionStorage.setItem('booted', '1') } catch { /* private mode */ }
  }
  const wait = quick ? 0 : Math.max(0, 1500 - performance.now())
  setTimeout(leave, wait)
  addEventListener('pointerdown', leave, { once: true })
  addEventListener('keydown', leave, { once: true })
}

/** Report whether an element is on screen, so endless motion can rest when it is not. */
export function useSeen<T extends Element>() {
  const ref = useRef<T>(null)
  useEffect(() => {
    const element = ref.current
    if (!element) return
    const observer = new IntersectionObserver(([entry]) => element.classList.toggle('seen', entry.isIntersecting))
    observer.observe(element)
    return () => observer.disconnect()
  }, [])
  return ref
}

/** The current time, refreshed while the page is visible. */
export function useNow(every = 30_000) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = setInterval(() => { if (!document.hidden) setNow(Date.now()) }, every)
    return () => clearInterval(timer)
  }, [every])
  return now
}

const SLOW = 120

/**
 * Page transitions need a snapshot of the page. A device that is slow to take it twice loses the
 * effect for this visit and keeps the lighter entrances.
 */
export function watchTransitions() {
  const start = document.startViewTransition?.bind(document)
  if (!start) return
  // The stand-in updates the page at once and takes no snapshot.
  const plain = (update?: ViewTransitionUpdateCallback) => {
    const done = Promise.resolve(update?.()).then(() => undefined)
    return { ready: done, finished: done, updateCallbackDone: done, skipTransition: () => undefined }
  }
  const off = () => { Object.defineProperty(document, 'startViewTransition', { value: plain, configurable: true }) }
  try { if (sessionStorage.getItem('light-motion')) return off() } catch { /* private mode */ }
  let strikes = 0
  const timed = (...args: Parameters<Document['startViewTransition']>) => {
    const began = performance.now()
    const transition = start(...args)
    transition.ready.then(() => {
      if (performance.now() - began <= SLOW || ++strikes < 2) return
      off()
      try { sessionStorage.setItem('light-motion', '1') } catch { /* private mode */ }
    }, () => { /* skipped */ })
    return transition
  }
  Object.defineProperty(document, 'startViewTransition', { value: timed, configurable: true })
}
