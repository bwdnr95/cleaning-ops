import React from 'react';

export function useIsNarrowViewport() {
  const [isNarrowViewport, setIsNarrowViewport] = React.useState(() => (
    typeof window !== 'undefined'
      ? window.matchMedia('(max-width: 768px)').matches
      : false
  ));

  React.useEffect(() => {
    const mediaQuery = window.matchMedia('(max-width: 768px)');
    const updateViewport = () => setIsNarrowViewport(mediaQuery.matches);
    updateViewport();
    mediaQuery.addEventListener('change', updateViewport);
    return () => mediaQuery.removeEventListener('change', updateViewport);
  }, []);

  return isNarrowViewport;
}
