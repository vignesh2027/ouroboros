/* Ask page (route #/ask; the marketing landing page is a separate document, landing.html). One headline, the ask box, the six cached example questions and one line of links.
   Nothing else: the sources, the steps and the score meaning live on How it works and in the footer. */
(function () {
  'use strict';
  var h = O.h;

  function build(el) {
    var composer = O.composer({
      large: true,
      placeholder: 'Ask a question',
      onSubmit: function (q, o) { try { composer.setValue(''); } catch (e) {} O.startThread({ question: q, guarded: o.guarded, hops: o.hops }); }
    });

    var hero = h('header', { class: 'hero' },
      h('h1', { class: 'hero-title' }, h('span', { class: 'br' }, 'Ask a question.'), h('span', { class: 'br hero-dim' }, 'See what the evidence says.')),
      h('p', { class: 'hero-sub' }, 'Answers with numbered sources, checked claim by claim.'),
      h('div', { class: 'hero-composer' }, composer.el));

    var examples = h('ul', { class: 'ex-list', 'aria-label': 'Example questions' }, O.EXAMPLES.map(function (q) {
      return h('li', null, h('button', { type: 'button', class: 'ex-item', onclick: function () { O.startThread({ question: q, guarded: true, hops: 4 }); } },
        h('span', null, q), O.icon('arrow-right', 18)));
    }));

    var links = h('p', { class: 'home-links' },
      h('a', { href: O.href('/audit') }, 'Have an answer from another AI? Check it.'),
      h('a', { href: O.href('/how') }, 'How it works'));

    el.append(h('div', { class: 'home' }, hero, h('div', { class: 'home-body' }, examples, links)));
    el._composer = composer;
  }

  O.route('ask', {
    title: '',
    init: build,
    show: function (el) {
      /* Focus the ask box on laptops, but never pop the keyboard up on a phone. */
      if (window.matchMedia && matchMedia('(min-width: 861px)').matches && el._composer) {
        setTimeout(function () { try { el._composer.input.focus({ preventScroll: true }); } catch (e) {} }, 60);
      }
    }
  });
})();
