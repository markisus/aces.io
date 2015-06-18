/*

  ractive-transitions-slidehorizontal
  =======================================================

  Version 1.0.0.

  A horizontal slide transition seems as useful as a vertical one...

  ==========================

  Troubleshooting: If you're using a module system in your app (AMD or
  something more nodey) then you may need to change the paths below,
  where it says `require( 'ractive' )` or `define([ 'ractive' ]...)`.

  ==========================

  Usage: Include this file on your page below Ractive, e.g:

      <script src='lib/ractive.js'></script>
          <script src='lib/ractive-transitions-slidehorizontal.js'></script>

	  Or, if you're using a module loader, require this module:

	      // requiring the plugin will 'activate' it - no need to use
	          // the return value
		      require( 'ractive-transitions-slidehorizontal' );

*/

(function ( global, factory ) {

    'use strict';

    // AMD environment
    if ( typeof define === 'function' && define.amd ) {
	define([ 'ractive' ], factory );
	}

    // Common JS (i.e. node/browserify)
    else if ( typeof module !== 'undefined' && module.exports && typeof require === 'function' ) {
	module.exports = factory( require( 'ractive' ) );
	}

    // browser global
    else if ( global.Ractive ) {
	factory( global.Ractive );
	}

    else {
	throw new Error( 'Could not find Ractive! It must be loaded before the ractive-transitions-slidehorizontal plugin' );
	}

}( typeof window !== 'undefined' ? window : this, function ( Ractive ) {

    'use strict';

    var slide, props, collapsed, defaults;

    defaults = {
	duration: 300,
	easing: 'easeInOut'
	};

    props = [
	'width',
	'borderLeftWidth',
	'borderRightWidth',
	'paddingLeft',
	'paddingRight',
	'marginLeft',
	'marginRight'
	];

    collapsed = {
	width: 0,
	borderLeftWidth: 0,
	borderRightWidth: 0,
	paddingLeft: 0,
	paddingRight: 0,
	marginLeft: 0,
	marginRight: 0
	};

    slide = function ( t, params ) {
	var targetStyle;

	params = t.processParams( params, defaults );

	if ( t.isIntro ) {
	    t.setStyle('height', t.getStyle('height'));
	    targetStyle = t.getStyle( props );
	    t.setStyle( collapsed );
	    } else {
		// make style explicit, so we're not transitioning to 'auto'
		t.setStyle('height', t.getStyle('height'));
		t.setStyle( t.getStyle( props ) );
		targetStyle = collapsed;
		}

	t.setStyle({
	    overflow: 'hidden'
	    });

	t.animateStyle( targetStyle, params ).then( t.complete );
	};
    Ractive.transitions.slidehorizontal = slide;
    Ractive.transitions.slideh = slide;
    return slide;
}));
