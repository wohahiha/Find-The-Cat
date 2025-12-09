<template>
  <div class="dark min-h-screen bg-background-dark text-text">
    <div class="relative min-h-screen">
      <div class="absolute inset-0 bg-background-dark"></div>
      <div class="absolute inset-0 bg-[radial-gradient(circle_at_center,_rgba(42,50,113,0.2),_transparent_42%)]"></div>
      <div class="relative z-10 flex min-h-screen items-center justify-center px-4 py-10">
        <router-view />
      </div>
    </div>
  </div>
</template>
