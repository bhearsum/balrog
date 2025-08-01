import { Auth0Provider } from '@auth0/auth0-react';
import CssBaseline from '@material-ui/core/CssBaseline';
import { ThemeProvider } from '@material-ui/styles';
import React, { Fragment } from 'react';
import Main from './Main';
import theme from './theme';

const App = () => {
  return (
    <Fragment>
      <CssBaseline />
      <Auth0Provider
        domain={process.env.AUTH0_DOMAIN}
        clientId={process.env.AUTH0_CLIENT_ID}
        redirectUri={process.env.AUTH0_REDIRECT_URI}
        audience={process.env.AUTH0_AUDIENCE}
        scope={process.env.AUTH0_SCOPE}
        authorizationParams={{
          audience: process.env.AUTH0_AUDIENCE,
          scope: process.env.AUTH0_SCOPE,
        }}
        leeway={30}
        cacheLocation="localstorage"
      >
        <ThemeProvider theme={theme}>
          <Main />
        </ThemeProvider>
      </Auth0Provider>
    </Fragment>
  );
};

export default App;
