import AppBar from '@material-ui/core/AppBar';
import Toolbar from '@material-ui/core/Toolbar';
import Typography from '@material-ui/core/Typography';
import { makeStyles } from '@material-ui/styles';
import { bool, node, string } from 'prop-types';
import React, { Fragment } from 'react';
import { Helmet } from 'react-helmet';
import { APP_BAR_HEIGHT, CONTENT_MAX_WIDTH } from '../../utils/constants';
import Link from '../../utils/Link';
import Button from '../Button';
import menuItems from './menuItems';
import SettingsMenu from './SettingsMenu';
import UserMenu from './UserMenu';

const useStyles = makeStyles((theme) => ({
  appbar: {
    height: APP_BAR_HEIGHT,
  },
  title: {
    textDecoration: 'none',
  },
  main: {
    maxWidth: CONTENT_MAX_WIDTH,
    height: '100%',
    margin: '0 auto',
    padding: `${theme.spacing(12)}px ${APP_BAR_HEIGHT}px`,
  },
  nav: {
    display: 'flex',
    flex: 1,
    justifyContent: 'flex-end',
    alignItems: 'center',
  },
  link: {
    textDecoration: 'none',
    color: 'inherit',
  },
  disabledLink: {
    textDecoration: 'none',
    color: theme.palette.grey[500],
    pointerEvents: 'none',
  },
  buttonWithIcon: {
    paddingLeft: theme.spacing(2),
  },
}));

export default function Dashboard(props) {
  const classes = useStyles();
  const { title, children, disabled } = props;

  return (
    <Fragment>
      <Helmet>
        <title>{title} - Balrog Admin</title>
      </Helmet>
      <AppBar className={classes.appbar}>
        <Toolbar>
          <Typography
            className={classes.title}
            color="inherit"
            variant="h6"
            noWrap
            component={Link}
            to="/"
          >
            Balrog Admin ┃ {title}
          </Typography>
          <nav className={classes.nav}>
            {menuItems.main.map((menuItem) => (
              <Link
                key={menuItem.value}
                className={disabled ? classes.disabledLink : classes.link}
                nav
                to={
                  window.location.pathname === menuItem.path
                    ? `${window.location.pathname}${window.location.search}`
                    : menuItem.path
                }
              >
                <Button color="inherit">{menuItem.value}</Button>
              </Link>
            ))}
            <SettingsMenu disabled={disabled} />
            <UserMenu />
          </nav>
        </Toolbar>
      </AppBar>
      <main className={classes.main}>{children}</main>
    </Fragment>
  );
}

Dashboard.prototype = {
  children: node.isRequired,
  // A title for the view.
  title: string.isRequired,
  disabled: bool,
};
