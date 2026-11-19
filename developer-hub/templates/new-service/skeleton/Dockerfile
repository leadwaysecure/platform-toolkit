FROM registry.access.redhat.com/ubi9/nginx-124:latest
# Replace with your app's build. Runs as non-root so it fits restricted-v2.
COPY index.html /opt/app-root/src/
EXPOSE ${{ values.port }}
CMD ["nginx", "-g", "daemon off;"]
