import React from 'react';

export function useApiResource(loader, dependencyKey = '') {
  const [data, setData] = React.useState(null);
  const [error, setError] = React.useState(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [reloadKey, setReloadKey] = React.useState(0);

  React.useEffect(() => {
    let isCurrent = true;
    setIsLoading(true);
    setError(null);

    loader()
      .then((result) => {
        if (isCurrent) {
          setData(result);
        }
      })
      .catch((requestError) => {
        if (isCurrent) {
          setError(requestError);
        }
      })
      .finally(() => {
        if (isCurrent) {
          setIsLoading(false);
        }
      });

    return () => {
      isCurrent = false;
    };
  }, [loader, dependencyKey, reloadKey]);

  return {
    data,
    error,
    isLoading,
    reload: () => setReloadKey((current) => current + 1),
  };
}
