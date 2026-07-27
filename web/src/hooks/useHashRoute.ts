import { useEffect, useState, useCallback } from 'react';

export interface Route {
  path: string;
  segments: string[];
}

/**
 * hash 路由：订阅 hashchange，避免"点链接不切换需刷新"的经典 bug。
 */
export function useHashRoute(): Route & { navigate: (to: string) => void } {
  const parse = useCallback((): Route => {
    const hash = window.location.hash.replace(/^#/, '');
    const path = hash.split('?')[0] || '/';
    const segments = path.split('/').filter(Boolean);
    return { path, segments };
  }, []);

  const [route, setRoute] = useState<Route>(parse);

  useEffect(() => {
    const onChange = () => setRoute(parse());
    window.addEventListener('hashchange', onChange);
    return () => window.removeEventListener('hashchange', onChange);
  }, [parse]);

  const navigate = useCallback((to: string) => {
    window.location.hash = to;
  }, []);

  return { ...route, navigate };
}
