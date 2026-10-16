def main():
    import uvicorn
    uvicorn.run('homecoming.app:app', host='127.0.0.1', port=8000, workers=1)


if __name__ == '__main__':
    main()
