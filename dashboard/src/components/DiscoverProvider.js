import React from 'react';
import axios from 'axios';
import PropTypes from 'prop-types';

import DiscoverContext from '../DiscoverContext';

class DiscoverProvider extends React.Component {
  static propTypes = {
    children: PropTypes.oneOfType([
      PropTypes.arrayOf(PropTypes.node),
      PropTypes.node
    ]).isRequired
  };
  state = {
    discover: []
  };

  refreshData = res => this.setState({ discover: res.data });

  constructor(props) {
    super(props);
    axios.get('/api/discover').then(this.refreshData);
  }

  render() {
    const { discover } = this.state;
    return (
      <DiscoverContext.Provider value={discover}>
        {this.props.children}
      </DiscoverContext.Provider>
    );
  }
}

export default DiscoverProvider;
